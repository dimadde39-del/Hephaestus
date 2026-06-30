# Config parser

`parse_config(values, environ=None)` accepts `debug` (`true`/`false`), `port`
(`1..65535`), and `mode` (`dev`, `prod`, `test`). `APP_*` environment values
override input values.
