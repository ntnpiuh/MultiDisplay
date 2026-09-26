from display.display_config import DisplayConfig, RefreshRate
from display.display_manager import DisplayManager


class NativeDescriptor:
    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self

    def __getattr__(self, name):
        if name.startswith("set") and name.endswith("_"):
            attribute = name[3:-1]
            return lambda value: setattr(self, attribute, value)
        raise AttributeError(name)


class NativeSettings:
    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self

    def setHiDPI_(self, value):
        self.hiDPI = value

    def setModes_(self, value):
        self.modes = value


class NativeMode:
    @classmethod
    def alloc(cls):
        return cls()

    def initWithWidth_height_refreshRate_(self, width, height, refresh):
        self.width, self.height, self.refresh = width, height, refresh
        return self


class NativeDisplay:
    @classmethod
    def alloc(cls):
        return cls()

    def initWithDescriptor_(self, descriptor):
        self.descriptor = descriptor
        self.id = 321
        self.released = False
        return self

    def displayID(self):
        return self.id

    def applySettings_(self, settings):
        self.settings = settings
        return True

    def release(self):
        self.released = True


class NativeCoreGraphics:
    @staticmethod
    def CGGetActiveDisplayList(*_):
        return 0, (321,), 1

    @staticmethod
    def CGDisplayCopyDisplayMode(_):
        return object()

    @staticmethod
    def CGDisplayModeGetRefreshRate(_):
        return 60.0

    @staticmethod
    def CGDisplayPixelsWide(_):
        return 1280

    @staticmethod
    def CGDisplayPixelsHigh(_):
        return 800


def test_manager_creates_a_hidpi_display_and_releases_it():
    manager = DisplayManager()
    manager._cg = NativeCoreGraphics
    manager._virtual_api = (NativeDescriptor, NativeDisplay, NativeSettings, NativeMode)

    display_id = manager.create_virtual_display(
        DisplayConfig("Tablet", 1280, 800, RefreshRate.HZ_60)
    )
    display = manager._virtual_displays[display_id]

    assert display_id == 321
    assert display.settings.hiDPI == 1
    assert (display.settings.modes[0].width, display.settings.modes[0].height) == (640, 400)
    assert manager.list_displays()[0].is_physical is False
    assert display.released is False
    assert manager.remove_virtual_display(display_id)
    assert display.released is True
    assert display_id not in manager._virtual_displays
    assert manager.list_displays()[0].is_physical is True


def test_manager_reconfigures_virtual_display_mode():
    manager = DisplayManager()
    manager._cg = NativeCoreGraphics
    manager._virtual_api = (NativeDescriptor, NativeDisplay, NativeSettings, NativeMode)
    display_id = manager.create_virtual_display(DisplayConfig("Tablet", 1280, 800))

    assert manager.configure_virtual_display(
        display_id, DisplayConfig("Tablet", 1600, 900, RefreshRate.HZ_30)
    )
    settings = manager._virtual_displays[display_id].settings
    assert settings.modes[0].width == 800
    assert settings.modes[0].height == 450
    assert settings.modes[0].refresh == 30.0


def test_manager_keeps_display_when_release_fails():
    manager = DisplayManager()
    manager._cg = NativeCoreGraphics
    manager._virtual_api = (NativeDescriptor, NativeDisplay, NativeSettings, NativeMode)
    display_id = manager.create_virtual_display(DisplayConfig("Tablet", 1280, 800))
    display = manager._virtual_displays[display_id]

    def fail_release():
        raise RuntimeError("release rejected")

    display.release = fail_release

    try:
        manager.remove_virtual_display(display_id)
    except RuntimeError as error:
        assert "Could not release virtual display 321" in str(error)
    else:
        raise AssertionError("release failure should be reported")
    assert display_id in manager._virtual_displays


def test_manager_reports_active_virtual_displays_with_snake_case_api():
    manager = DisplayManager()
    manager._cg = NativeCoreGraphics
    manager._virtual_api = (NativeDescriptor, NativeDisplay, NativeSettings, NativeMode)
    display_id = manager.create_virtual_display(DisplayConfig("Tablet", 1280, 800))

    assert manager.get_active_displays() == [display_id]
