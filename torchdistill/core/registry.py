PROC_FUNC_DICT = dict()


def register_forward_proc_func(arg=None, **kwargs):
    def _register_forward_proc_func(func):
        key = kwargs.get('key')
        if key is None:
            key = func.__name__

        PROC_FUNC_DICT[key] = func
        return func

    if callable(arg):
        return _register_forward_proc_func(arg)
    return _register_forward_proc_func


def get_forward_proc_func(func_name):
    if func_name is None:
        return PROC_FUNC_DICT['forward_batch_only']
    elif func_name in PROC_FUNC_DICT:
        return PROC_FUNC_DICT[func_name]
    raise ValueError('No forward process function `{}` registered'.format(func_name))