// SPDX-License-Identifier: GPL-2.0
/* Minimal raw MTD writer: erase + write + verify. */
#include <errno.h>
#include <fcntl.h>
#include <mtd/mtd-user.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	struct mtd_info_user mi;
	struct stat st;
	unsigned char *buf, *chk;
	size_t len, off;
	ssize_t n;
	int fd, mfd, ret = 1;

	if (argc != 3) {
		fprintf(stderr, "usage: %s <mtddev> <file>\n", argv[0]);
		return 2;
	}

	fd = open(argv[2], O_RDONLY);
	if (fd < 0) {
		perror("open image");
		return 2;
	}
	if (fstat(fd, &st) || st.st_size <= 0) {
		perror("stat image");
		return 2;
	}
	len = st.st_size;

	buf = malloc(len);
	chk = malloc(65536);
	if (!buf || !chk) {
		fprintf(stderr, "out of memory\n");
		return 2;
	}
	for (off = 0; off < len; ) {
		n = read(fd, buf + off, len - off);
		if (n <= 0) {
			perror("read image");
			return 2;
		}
		off += n;
	}
	close(fd);

	mfd = open(argv[1], O_RDWR | O_SYNC);
	if (mfd < 0) {
		perror("open mtd");
		return 2;
	}
	if (ioctl(mfd, MEMGETINFO, &mi)) {
		perror("MEMGETINFO");
		return 2;
	}
	printf("mtd: size=0x%x erasesize=0x%x writesize=0x%x\n",
	       mi.size, mi.erasesize, mi.writesize);
	if (len > mi.size) {
		fprintf(stderr, "image (%zu) larger than mtd (%u)\n", len, mi.size);
		return 2;
	}

	for (off = 0; off < len; off += mi.erasesize) {
		struct erase_info_user ei = {
			.start = off,
			.length = mi.erasesize,
		};
		if (ioctl(mfd, MEMERASE, &ei)) {
			fprintf(stderr, "erase 0x%zx: %s\n", off, strerror(errno));
			return 1;
		}
	}
	printf("erased %zu bytes\n", (len + mi.erasesize - 1) / mi.erasesize * mi.erasesize);

	for (off = 0; off < len; ) {
		size_t chunk = len - off > 65536 ? 65536 : len - off;
		if (lseek(mfd, off, SEEK_SET) < 0) {
			perror("lseek write");
			return 1;
		}
		n = write(mfd, buf + off, chunk);
		if (n != (ssize_t)chunk) {
			fprintf(stderr, "write 0x%zx: %zd (%s)\n", off, n, strerror(errno));
			return 1;
		}
		off += chunk;
	}
	fsync(mfd);
	printf("wrote %zu bytes, verifying...\n", len);

	for (off = 0; off < len; ) {
		size_t chunk = len - off > 65536 ? 65536 : len - off;
		if (lseek(mfd, off, SEEK_SET) < 0) {
			perror("lseek read");
			return 1;
		}
		n = read(mfd, chk, chunk);
		if (n != (ssize_t)chunk) {
			fprintf(stderr, "readback 0x%zx: %zd (%s)\n", off, n, strerror(errno));
			return 1;
		}
		if (memcmp(buf + off, chk, chunk)) {
			fprintf(stderr, "verify mismatch at 0x%zx\n", off);
			return 1;
		}
		off += chunk;
	}

	printf("VERIFY OK\n");
	ret = 0;
	close(mfd);
	return ret;
}
