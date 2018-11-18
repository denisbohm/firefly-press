from intelhex import IntelHex
import os
from pynrfjprog import MultiAPI
import struct
import time
from datetime import datetime


class Program:

    def __init__(self):
        self.FLASH_PAGE_SIZE = 4096

        self.MANUFACTURING_INFORMATION_MAGIC = 0x6f686365

        self.UICR = 0x10001000
        self.BOOTLOADERADDR = 0x014
        self.CUSTOMER = 0x080
        self.PSELRESET0 = 0x200
        self.PSELRESET1 = 0x204
        self.APPROTECT = 0x208
        self.NFCPINSADDR = 0x20C

    @staticmethod
    def verify(api, address, data):
        verify_data = api.read(address, len(data))
        if len(data) != len(verify_data):
            print("invalid verify data length read back")
            raise Exception()
        for i in range(0, len(data)):
            if data[i] != verify_data[i]:
                print("invalid verify " + ("0x%0.2X" % verify_data[i]) + " at offset " + str(i) + " in " + str(len(data)) + " expected " + ("0x%0.2X" % data[i]))
                raise Exception()

    @staticmethod
    def program_file(api, path):
        intel_hex = IntelHex(path)
        segments = intel_hex.segments()
        address = segments[0][0]
        address_end = segments[-1][1]
        size = address_end - address
        print("programming " + path + " " + str(size) + " bytes at " + ("0x%0.8X" % address))
        data = intel_hex.tobinarray(start=address, size=size)
        api.write(address, data, True)
        Program.verify(api, address, data)
        return address

    @staticmethod
    def replace(collection, start, replacement):
        collection[start:start + len(replacement)] = replacement

    @staticmethod
    def replace_uint32(collection, start, value):
        Program.replace(collection, start, struct.pack("<I", value))

    def set_manufacturing_information(self, uicr_data, bootloader_address, date, serial_number):
        Program.replace_uint32(uicr_data, self.BOOTLOADERADDR, bootloader_address)

        pselreset = 21
        Program.replace_uint32(uicr_data, self.PSELRESET0, pselreset)
        Program.replace_uint32(uicr_data, self.PSELRESET1, pselreset)

        ncfpins = 0xfffffffe  # NCF pins operate as GPIO (not as NCF)
        Program.replace_uint32(uicr_data, self.NFCPINSADDR, ncfpins)

        unix_time = int(time.mktime(date.timetuple()))
        manufacturing_information = bytearray(struct.pack(
            '<III', self.MANUFACTURING_INFORMATION_MAGIC, unix_time, len(serial_number)
        ))
        manufacturing_information.extend(serial_number)
        Program.replace(uicr_data, self.CUSTOMER, manufacturing_information)

    def program(self, mcu, boot, others, serial_number, protect):
        api = MultiAPI.MultiAPI(mcu)
        api.open()
        api.connect_to_emu_without_snr()
        api.recover()

        bootloader_address = Program.program_file(api, boot)
        for other in others:
            Program.program_file(api, other)

        print("programming UICR " + str(self.FLASH_PAGE_SIZE) + " bytes at " + ("0x%0.8X" % self.UICR))
        uicr_data = api.read(self.UICR, self.FLASH_PAGE_SIZE)

        now = datetime.now()
        self.set_manufacturing_information(uicr_data, bootloader_address, now, serial_number)

        if protect:
            print("enabling SWD protection, power cycle PCBA for this to take effect")
            Program.replace_uint32(uicr_data, self.APPROTECT, 0xffffff00)

        api.write(self.UICR, uicr_data, True)
        Program.verify(api, self.UICR, uicr_data)

        print("resetting device")
        api.debug_reset()

        api.close()

    @staticmethod
    def get_production_files(path):
        all_files = [os.path.join(path, s) for s in os.listdir(path)]
        files = [a_file for a_file in all_files if a_file.endswith('.hex')]
        boot = next(a_file for a_file in files if 'boot' in a_file)
        others = [a_file for a_file in files if not a_file == boot]
        return boot, others

