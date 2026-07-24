# Changelog

## [0.2.2](https://github.com/KRoperUK/uw-py/compare/v0.2.1...v0.2.2) (2026-07-24)


### Bug Fixes

* add pdfplumber to dev extras, relax test assertion ([52ae2a9](https://github.com/KRoperUK/uw-py/commit/52ae2a9731907ecb1590bf16882786a5e04630c9))
* move pdfplumber to optional dev dependency ([cd79959](https://github.com/KRoperUK/uw-py/commit/cd79959e1fe693424398993805ba58c0180499bf))
* relax pydantic constraint to &gt;=2.0 ([1d4014c](https://github.com/KRoperUK/uw-py/commit/1d4014ce4f7c39ace650d05e07e831d0f0354233))

## [0.2.1](https://github.com/KRoperUK/uw-py/compare/v0.2.0...v0.2.1) (2026-07-23)


### Bug Fixes

* lazy httpx.AsyncClient creation to avoid blocking SSL init ([ad96276](https://github.com/KRoperUK/uw-py/commit/ad962764820c7f37983ca0fb9f215e1742ae382a))
* point pip cache at pyproject.toml, not ci.yml ([f94f388](https://github.com/KRoperUK/uw-py/commit/f94f38898ba96bc6ff2eb29f35fc30fc12e4320d))

## [0.2.0](https://github.com/KRoperUK/uw-py/compare/v0.1.0...v0.2.0) (2026-07-23)


### Features

* initial uw-py library implementation ([5f36ca3](https://github.com/KRoperUK/uw-py/commit/5f36ca3b37e35da3d4949114cc7f212b5673c702))


### Bug Fixes

* add mypy files directive to pyproject.toml ([76aab40](https://github.com/KRoperUK/uw-py/commit/76aab4071d0196af16628620a56ac6a179cf9384))
* add pytest-cov and pytest-xdist to dev dependencies ([59ed97f](https://github.com/KRoperUK/uw-py/commit/59ed97fd1dea1fa711b019d0e7a5e2910ceb9c66))
* drop test matrix so check name matches branch protection ([bb04962](https://github.com/KRoperUK/uw-py/commit/bb0496250368e767779c5a9ca599744601a0938f))


### Documentation

* update README with hardcoded endpoints, API reference ([2e567bc](https://github.com/KRoperUK/uw-py/commit/2e567bca9d407f75dbc0987df6212cc2c74ae30e))
