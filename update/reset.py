from pynrfjprog import MultiAPI


class Reset:

    def __init__(self):
        pass

    @staticmethod
    def pin_reset():
        api = MultiAPI.MultiAPI('NRF52')
        api.open()
        api.connect_to_emu_without_snr()

        print("resetting device")
        api.pin_reset()

        api.close()
