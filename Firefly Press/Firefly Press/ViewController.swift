//
//  ViewController.swift
//  Firefly Press
//
//  Created by Denis Bohm on 11/11/18.
//  Copyright © 2018 Firefly Design LLC. All rights reserved.
//

import Cocoa
import CoreBluetooth

class ViewController: NSViewController, BluetoothDelegate {

    @IBOutlet var heatButton: NSButton!
    @IBOutlet var setpointStepper: NSStepper!
    @IBOutlet var setpointTextField: NSTextField!
    @IBOutlet var temperatureTextField: NSTextField!

    var bluetooth: Bluetooth = Bluetooth()
    
    override func viewDidLoad() {
        super.viewDidLoad()

        bluetooth.start(delegate: self, serviceUuid: CBUUID(string: "577FB8B4-553E-4807-9779-8647481D49B3"))
    }
    
    func sendControl() {
        let heat = heatButton.state == .on
        let setpoint = setpointStepper.intValue
        let value = Data([
            heat ? 0x01 : 0x00,
            UInt8(truncating: NSNumber(value: setpoint)),
            UInt8(truncating: NSNumber(value: setpoint >> 8))
            ])
        guard let characteristic = bluetooth.getCharacteristic(uuid: 0x0003) else {
            return
        }
        bluetooth.peripheral?.writeValue(value, for: characteristic, type: .withoutResponse)
    }
    
    @IBAction func heatButtonChanged(sender: NSButton) {
        sendControl()
    }
    
    @IBAction func setpointStepperChanged(sender: NSStepper) {
        sendControl()
    }

    func bluetooth(bluetooth: Bluetooth, characteristic: CBCharacteristic, value: Data?) {
        guard let value = value, value.count >= 5 else {
            return
        }
        let heat = (value[0] & 0b1) != 0
        let setpoint = (UInt16(value[2]) << 8) | UInt16(value[1])
        let temperature = (UInt16(value[4]) << 8) | UInt16(value[3])
        heatButton.state = heat ? .on : .off
        setpointTextField.stringValue = String(setpoint)
        setpointStepper.intValue = Int32(setpoint)
        temperatureTextField.stringValue = String(temperature)
    }
    
}
