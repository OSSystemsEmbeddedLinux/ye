def __after_init_ye_yocto():
    PLATFORM_ROOT_DIR = os.environ['PLATFORM_ROOT_DIR']
    yedir = os.path.join(PLATFORM_ROOT_DIR, 'sources', 'ye')
    os.environ['PATH'] = os.environ['PATH'] + ':' + yedir

run_after_init(__after_init_ye_yocto)
