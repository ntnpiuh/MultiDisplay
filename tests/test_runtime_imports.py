import importlib


def test_main_module_imports():
    main_module = importlib.import_module("main")
    assert hasattr(main_module, "main")


def test_multidisplay_entry_point_module_imports():
    multidisplay_module = importlib.import_module("multidisplay.main")
    assert hasattr(multidisplay_module, "main")
