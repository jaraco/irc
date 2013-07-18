from __future__ import absolute_import, print_function, unicode_literals

import functools
import collections

def save_method_args(method):
    """
    Wrap a method such that when it is called, we save the args and
    kwargs with which it was called.

    >>> class MyClass(object):
    ...     @save_method_args
    ...     def method(self, a, b):
    ...         print(a, b)
    >>> my_ob = MyClass()
    >>> my_ob.method(1, 2)
    1 2
    >>> my_ob._saved_method.args
    (1, 2)
    >>> my_ob._saved_method.kwargs
    {}
    >>> my_ob.method(a=3, b='foo')
    3 foo
    >>> my_ob._saved_method.args
    ()
    >>> my_ob._saved_method.kwargs == dict(a=3, b='foo')
    True
    """
    args_and_kwargs = collections.namedtuple('args_and_kwargs', 'args kwargs')
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        attr_name = '_saved_' + method.__name__
        attr = args_and_kwargs(args, kwargs)
        setattr(self, attr_name, attr)
        return method(self, *args, **kwargs)
    return wrapper
