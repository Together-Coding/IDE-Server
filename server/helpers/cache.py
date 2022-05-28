import functools
import hashlib
import inspect
import pickle
from typing import Any, Callable

import redis

from configs import settings

r = redis.StrictRedis.from_url(
    settings.REDIS_URL,
    db=settings.CACHE_REDIS_DB,
)


class Cache:
    def __init__(
        self,
        instance_attr_names: list | None = None,
    ):
        """Initialize Cache object

        Args:
            instance_attr_names (list | None, optional): default attributes used to make cache key. Defaults to None.
        """

        self.instance_attr_names = instance_attr_names
        self.log = lambda *args: print(*args) if settings.DEBUG else lambda _: _

    def _dumps(self, value: Any) -> bytes:
        return pickle.dumps(value)

    def _loads(self, value: bytes) -> Any:
        return pickle.loads(value)

    def set_raw(self, key, value):
        r.set(key, self._dumps(value))

    def load_raw(self, key):
        return self._loads(r.get(key))

    def cached(self, timeout: int | None = None, key_prefix: str = ""):
        """Cache the decorated function. This method ignores the parameters passed to the function.
        Thus, all requests of the same function has same result. If parameter should be considered,
        use ``memoized`` method instead.

        Args:
            timeout (int | None, optional): Time to live in seconds. Defaults to None.
            key_prefix (str, optional): prefix of the cached key. Defaults to "".
        """

        def wrapper(f: Callable):
            @functools.wraps(f)
            def decorated(*args, **kwargs):
                cache_key = f"{key_prefix}.{f.__module__}.{f.__qualname__}"
                self.log(cache_key)

                _result = r.get(cache_key)
                if _result is not None:
                    result = self._loads(_result)
                    return result

                _result = f(*args, **kwargs)
                result = self._dumps(_result)
                r.set(cache_key, result, timeout)

                return _result

            return decorated

        return wrapper

    @staticmethod
    def get_arg_names(f: Callable) -> list[str]:
        return [p.name for p in inspect.signature(f).parameters.values()]

    def _make_param_key(self, f: Callable, ignore_args: list, *args, **kwargs):
        """Make key with parameters"""

        md5 = hashlib.md5()

        # Remove args to ignore
        arg_names = self.get_arg_names(f)
        new_args = []
        add = []
        for _arg, _name in zip(args, arg_names):
            if _name == "self":
                # Add instance attributes
                if self.instance_attr_names:
                    for name in self.instance_attr_names:
                        add.append(f"{getattr(args[0], name, None)}")
                continue

            if _name not in ignore_args:
                new_args.append(_arg)

        # Make key
        md5.update(f"{new_args}{kwargs}{add}".encode())

        return md5.hexdigest()

    def make_cache_key(self, f: Callable, ignore_args: list, *args, **kwargs):
        param_key = self._make_param_key(f, ignore_args, *args, **kwargs)
        return f"_:{f.__module__}:{f.__qualname__}:{param_key}"

    def memoize(
        self,
        timeout: int | None = None,
        ignore_args: list | None = None,
    ):
        """Memoize the decorated function considering its parameters

        Args:
            timeout (int | None, optional): Time to live in seconds. Defaults to None.
            key_prefix (str, optional): prefix of the cached key. Defaults to "".
        """

        def wrapper(f: Callable):
            @functools.wraps(f)
            def decorated(*args, **kwargs):
                cache_key = self.make_cache_key(f, ignore_args, *args, **kwargs)
                self.log(cache_key)

                _result = r.get(cache_key)
                if _result is not None:
                    self.log("# HIT")
                    result = self._loads(_result)
                    return result

                # Note: return value ``None`` is not cached.
                _result = f(*args, **kwargs)
                result = self._dumps(_result)
                r.set(cache_key, result, timeout)

                return _result

            return decorated

        if ignore_args is None:
            ignore_args = []

        return wrapper

    def delete_memoize(self, f: Callable, *args, **kwargs):
        cache_key = self.make_cache_key(f, [], *args, **kwargs)
        self.log("# DELETE MEMOIZE", cache_key)

        r.delete(cache_key)

    def delete_memoize_with_ignore(self, f: Callable, ignore_args: list, *args, **kwargs):
        cache_key = self.make_cache_key(f, ignore_args, *args, **kwargs)
        self.log("# DELETE MEMOIZE", cache_key)

        r.delete(cache_key)


course_cache = Cache(instance_attr_names=["course_id"])
lesson_cache = Cache(instance_attr_names=["course_id", "lesson_id"])
ptc_cache = Cache(instance_attr_names=["course_id", "lesson_id", "user_id"])
