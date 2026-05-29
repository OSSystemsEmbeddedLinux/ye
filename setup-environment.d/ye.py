import os


def __after_init_ye_yocto():
    PLATFORM_ROOT_DIR = os.environ['PLATFORM_ROOT_DIR']
    candidates = [
        os.path.join(PLATFORM_ROOT_DIR, 'sources', 'ye'),
        os.path.join(PLATFORM_ROOT_DIR, 'layers', 'ye'),
        os.path.join(PLATFORM_ROOT_DIR, 'ye'),
    ]
    for yedir in candidates:
        if os.path.exists(os.path.join(yedir, 'ye')):
            os.environ['PATH'] = os.environ['PATH'] + ':' + yedir
            break

run_after_init(__after_init_ye_yocto)
