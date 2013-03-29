VERSION=0.6
PREFIX=/usr/local
BUILD_DIR=$(DESTDIR)$(PREFIX)
BIN_DIR=$(BUILD_DIR)/bin
MAN_DIR=$(BUILD_DIR)/share/man/man1
SHARE_DIR=$(BUILD_DIR)/share/gslimp3
FINAL_SHARE_DIR=$(PREFIX)/share/gslimp3

all:

install:
	python setup.py install --prefix=$(BUILD_DIR)

	install -d $(BIN_DIR)
	install -d $(MAN_DIR)
	install -d $(SHARE_DIR)

	sed -e 's#@SHARE_DIR@#$(FINAL_SHARE_DIR)#' gslimp3 > gslimp3.tmp
	install -m 755 gslimp3.tmp $(BIN_DIR)/gslimp3
	rm -f gslimp3.tmp

	sed -e 's/@VERSION@/$(VERSION)/' gslimp3.glade > gslimp3.glade.tmp
	install -m 644 gslimp3.glade.tmp $(SHARE_DIR)/gslimp3.glade
	rm -f gslimp3.glade.tmp

	install -m 644 lcd_chars.txt $(SHARE_DIR)/lcd_chars.txt

	sed -e 's/@VERSION@/$(VERSION)/' gslimp3.1 | gzip -c9 - > gslimp3.1.gz.tmp
	install -m 644 gslimp3.1.gz.tmp $(MAN_DIR)/gslimp3.1.gz
	rm -f gslimp3.1.gz.tmp

clean:
	rm -f *~
	rm -f *.pyc
	rm -rf build
	rm -f *.tmp

.PHONY: all install clean
