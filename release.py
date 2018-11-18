#!/usr/bin/env python3

from update.encrypt import Encrypt
from update.encrypt import Version
from update.program import Program
from update.source import Source

import argparse
import os
import shutil
import subprocess
from time import sleep


def cmd_output(args, **kwds):
    kwds.setdefault("stdout", subprocess.PIPE)
    kwds.setdefault("stderr", subprocess.STDOUT)
    child = subprocess.Popen(args, **kwds)
    output = child.communicate()
    stdout = output[0].decode("utf-8")
    if child.returncode != 0:
        raise ValueError("command failed: " + stdout)
    return stdout


def crossbuild(solution, project, type="Release"):
    cmd_output(
        ["crossbuild", "-config", "THUMB " + type, "-project", project, "-rebuild", solution + ".hzp"]
    )
    return project + " THUMB " + type + "/" + project + ".hex"


def build(solution, project, type="Release"):
    if shutil.which("crossbuild") is not None:
        return crossbuild(solution, project, type)
    # add more build commands here (iar, etc) -denis
    raise ValueError("build command not found")


def main(solution, do_compile, do_program, serial_number, protect):
    release = "release/"

    if do_compile:
        print("updating git hash in src/boot.c")
        Source.replace_commit("src/boot.c")
        print("compiling project boot")
        boot_hex_file = build(solution, "boot", "Release")

        print("copying boot to release directory")
        if not os.path.exists(release):
            os.makedirs(release)
        shutil.copy2(boot_hex_file, release + "/boot.hex")
        shutil.copy2("nRF5_SDK/components/softdevice/s140/hex/s140_nrf52_6.1.0_softdevice.hex", release)

        print("updating git hash in src/main.c")
        Source.replace_commit("src/main.c")
        print("compiling project main")
        application_hex_file = build(solution, "main", "Debug")

        print("encrypting main binary and placing result into release directory")
        firmware_path = application_hex_file
        encrypted_firmware_path = "release/main.bin"
        key = Source.find_data("src/key.c")
        version_major = Source.find_int("src/main.c", "major")
        version_minor = Source.find_int("src/main.c", "minor")
        version_revision = Source.find_int("src/main.c", "revision")
        version_commit = Source.find_data("src/main.c")
        version = Version(major=version_major, minor=version_minor, revision=version_revision, commit=version_commit)
        comment = "main"
        Encrypt.encrypt(firmware_path, key, version, comment, encrypted_firmware_path)

    if do_program:
        print("programming release via SWD")
        boot, others = Program.get_release_files(release)
        program = Program()
        program.program("NRF52", boot, others, serial_number.encode("utf-8"), protect)
        sleep(1)


def add_bool_option(parser, name, default, help):
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--" + name, dest=name, action="store_true", help=help)
    group.add_argument("--no-" + name, dest=name, action="store_false")

parser = argparse.ArgumentParser(description="release process for nRF52 based application with boot loader and softdevice")
add_bool_option(parser, "compile", False, help="compile firmware, encrypt application, and place results in the release directory")
add_bool_option(parser, "program", False, help="program the device with the boot loader, softdevice, UICR, manufacturing information, main application, etc, based on the contents of the release directory")
add_bool_option(parser, "protect", False, help="when programming, also enable SWD access port protection (using UICR APPROTECT on nRF52)")
parser.add_argument("--solution", help="CrossWorks solution name")
parser.add_argument("--serial_number", help="device serial number (ex: FD000001) (programmed into manufacturing information area)")
parser.set_defaults(compile=True, program=True, protect=False, solution="press", serial_number="FD000001")

args = parser.parse_args()
main(solution=args.solution, do_compile=args.compile, do_program=args.program, serial_number=args.serial_number, protect=args.protect)
