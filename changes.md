# Versions

---

## Version 1.0.2

### Minor Changes:
> - Error code feature of all exceptions. It generates an error code and appends on the error message.

---

## Version 1.0.1

### Minor Changes:
> - Allow lazy referencing via `LazyRef`.

---

## Version 1.0.0

### Major Changes:
> - Lazily loads all providers specified:
>   > - `Factory` provider for creating multiple instances.
>   > - `Singleton` provider for creating only one global instance.
> - Allows creating dependency containers or sub-containers for parent containers with the use of `Dependency`.
> - Allows explicit lifecycle management of a service with the use of `Resource`. It works with either awaitable or non-awaitable functions.
