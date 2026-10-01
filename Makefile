PACKAGE_NAME = agency.zip

.PHONY: all build clean test

all: build

clean:
	rm -f $(PACKAGE_NAME)

build: clean
	zip -r $(PACKAGE_NAME) -@ < zip_list.txt
