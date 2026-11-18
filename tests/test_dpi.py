"""dpi-review-001: 실험용 DPI 인식 플래그와 배율 도우미(창 없음)."""
import unittest
from unittest.mock import patch

from aidc.ui import dpi


class FakeApi:
    def __init__(self, result=0, actual=1, system_dpi=120, raise_on=None):
        self.result, self.actual, self.dpi, self.raise_on = result, actual, system_dpi, raise_on
        self.calls = []

    def set_process_awareness(self, value):
        self.calls.append(('set', value))
        if self.raise_on == 'set':
            raise OSError('set failed')
        return self.result

    def process_awareness(self):
        self.calls.append(('get',))
        return self.actual

    def system_dpi(self):
        self.calls.append(('dpi',))
        if self.raise_on == 'dpi':
            raise OSError('dpi failed')
        return self.dpi


class DpiFlagTests(unittest.TestCase):
    def setUp(self):
        dpi._reset()
        self.addCleanup(dpi._reset)

    def test_default_is_unaware_with_identity_scale(self):
        self.assertEqual(dpi.status()['mode'], 'unaware')
        self.assertEqual(dpi.scale(), 1.0)
        self.assertEqual(dpi.px(820), 820)
        self.assertIsInstance(dpi.px(820), int)
        self.assertEqual(dpi.px(12.5), 12.5)
        self.assertEqual(dpi.size((1000, 650)), (1000, 650))
        self.assertEqual(dpi.geometry('1000x650+40+20'), '1000x650+40+20')
        self.assertEqual(dpi.unpx(190), 190)

    def test_flag_is_read_only_from_explicit_system_value(self):
        self.assertTrue(dpi.requested({'SRS_DPI_AWARE': 'system'}))
        self.assertTrue(dpi.requested({'SRS_DPI_AWARE': ' System '}))
        for value in ('', '0', '1', 'on', 'per-monitor', 'pmv2'):
            self.assertFalse(dpi.requested({'SRS_DPI_AWARE': value}), value)
        self.assertFalse(dpi.requested({}))

    def test_without_flag_no_windows_call_is_made(self):
        api = FakeApi()
        self.assertFalse(dpi.configure_from_environment({}, api))
        self.assertEqual(api.calls, [])
        self.assertEqual(dpi.scale(), 1.0)

    def test_success_uses_system_dpi_only_after_checking_actual_state(self):
        api = FakeApi(system_dpi=120)
        self.assertTrue(dpi.configure_from_environment({'SRS_DPI_AWARE': 'system'}, api))
        self.assertEqual(api.calls, [('set', 1), ('get',), ('dpi',)])
        self.assertEqual(dpi.status()['mode'], 'system')
        self.assertEqual(dpi.scale(), 1.25)
        self.assertEqual(dpi.px(820), 1025)
        self.assertEqual(dpi.px(7), 9)
        self.assertEqual(dpi.size((1000, 650)), (1250, 812))
        self.assertEqual(dpi.geometry('1000x650+40+20'), '1250x812+50+25')
        self.assertEqual(dpi.unpx(1025), 820)

    def test_other_scales(self):
        for value, expected in ((96, 1.0), (144, 1.5), (168, 1.75), (192, 2.0)):
            dpi._reset()
            self.assertTrue(dpi.enable_system_awareness(FakeApi(system_dpi=value)))
            self.assertEqual(dpi.scale(), expected)

    def test_failed_call_keeps_identity_scale(self):
        cases = {
            'hresult': FakeApi(result=-2147024809, actual=0),  # E_INVALIDARG
            'still unaware': FakeApi(result=0, actual=0),
            'per monitor already': FakeApi(result=dpi.E_ACCESSDENIED, actual=2),
            'unknown state': FakeApi(result=0, actual=None),
            'set raises': FakeApi(raise_on='set'),
            'dpi raises': FakeApi(raise_on='dpi'),
            'zero dpi': FakeApi(system_dpi=0),
            'huge dpi': FakeApi(system_dpi=5000),
        }
        for name, api in cases.items():
            with self.subTest(name=name):
                dpi._reset()
                self.assertFalse(dpi.enable_system_awareness(api))
                self.assertEqual(dpi.scale(), 1.0)
                self.assertEqual(dpi.status()['mode'], 'unaware')
                self.assertTrue(dpi.status()['reason'])

    def test_access_denied_is_accepted_only_when_already_system_aware(self):
        self.assertTrue(dpi.enable_system_awareness(FakeApi(result=dpi.E_ACCESSDENIED, actual=1)))
        self.assertEqual(dpi.scale(), 1.25)

    def test_second_call_does_not_touch_windows_again(self):
        self.assertTrue(dpi.enable_system_awareness(FakeApi()))
        again = FakeApi(system_dpi=192)
        self.assertTrue(dpi.enable_system_awareness(again))
        self.assertEqual(again.calls, [])
        self.assertEqual(dpi.scale(), 1.25)

    def test_non_windows_is_a_safe_no_op(self):
        with patch('aidc.ui.dpi.sys.platform', 'linux'):
            self.assertFalse(dpi.enable_system_awareness())
        self.assertEqual(dpi.scale(), 1.0)

    def test_canvas_helpers_scale_coordinates_only_when_aware(self):
        class FakeCanvas:
            scaled = None
            def winfo_width(self): return 500
            def winfo_height(self): return 250
            def scale(self, *args): self.scaled = args
        canvas = FakeCanvas()
        dpi.finish_canvas(canvas)
        self.assertIsNone(canvas.scaled)
        self.assertEqual(dpi.logical_size(canvas), (500, 250))
        dpi.enable_system_awareness(FakeApi())
        dpi.finish_canvas(canvas)
        self.assertEqual(canvas.scaled, ('all', 0, 0, 1.25, 1.25))
        self.assertEqual(dpi.logical_size(canvas), (400, 200))


class MainEntryTests(unittest.TestCase):
    def setUp(self):
        dpi._reset()
        self.addCleanup(dpi._reset)

    def test_main_configures_dpi_before_creating_tk(self):
        import main
        order = []
        with patch.object(main.dpi, 'configure_from_environment', side_effect=lambda: order.append('dpi')), \
             patch.object(main.tk, 'Tk', side_effect=lambda: order.append('tk') or StopMain()), \
             patch.object(main, 'ModeSelection', side_effect=StopMain):
            with self.assertRaises(StopMain):
                main.main()
        self.assertEqual(order[:2], ['dpi', 'tk'])

    def test_default_launch_stays_unaware(self):
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('SRS_DPI_AWARE', None)
            self.assertFalse(dpi.configure_from_environment())
        self.assertEqual(dpi.status()['mode'], 'unaware')
        self.assertEqual(dpi.scale(), 1.0)


class StopMain(Exception):
    pass


if __name__ == '__main__':
    unittest.main()
