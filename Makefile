BUILD_DIR ?= build
GENERATOR ?= MinGW Makefiles

.PHONY: all configure build clean

all: build

configure:
	cmake -S . -B $(BUILD_DIR) -G "$(GENERATOR)" -DCMAKE_BUILD_TYPE=Release

build: configure
	cmake --build $(BUILD_DIR) --config Release

clean:
	cmake -E rm -rf $(BUILD_DIR)
