LUA_DIR := vendor/lua-5.4.7
QJS_DIR := vendor/quickjs-2025-04-26

CFLAGS := -O2 -Wall -Wextra -std=c11
LDLIBS := -lm

.PHONY: all run clean sizes

all: bench_lua bench_quickjs

bench_lua: bench_lua.c frame.h
	$(CC) $(CFLAGS) -I$(LUA_DIR)/src -o $@ $< $(LUA_DIR)/src/liblua.a $(LDLIBS)

bench_quickjs: bench_quickjs.c frame.h
	$(CC) $(CFLAGS) -I$(QJS_DIR) -o $@ $< $(QJS_DIR)/libquickjs.a $(LDLIBS) -lpthread

run: all
	@./bench_lua; echo; ./bench_quickjs

sizes: all
	@echo "stripped binary size (harness + engine, static):"
	@for b in bench_lua bench_quickjs; do \
		cp $$b $$b.stripped && strip $$b.stripped && \
		printf "  %-16s %s\n" $$b "$$(du -h $$b.stripped | cut -f1)"; \
		rm -f $$b.stripped; \
	done

clean:
	rm -f bench_lua bench_quickjs *.stripped
