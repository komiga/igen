
## igen

A "simple" interface generator using libclang/cindex.py and Mako. Use is
straightforward. See `igen --help` and `src/igen/igen.py`.

`-fsyntax-only` is a good default, especially if you are including the very
code you're generating and relying on it in some manner for declarations at
compile-time. Name resolution in that context won't fail, and it should be
faster to execute as well.

## License

igen carries the MIT license, which can be found in the `LICENSE` file.

