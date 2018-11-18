//
//  Bluetooth.swift
//  Simple Bluetooth
//
//  Created by Denis Bohm on 11/7/17.
//  Copyright © 2017 Firefly Design. All rights reserved.
//

import CoreBluetooth
import Dispatch

protocol BluetoothDelegate {
    
    func bluetooth(bluetooth: Bluetooth, characteristic: CBCharacteristic, value: Data?);
    
}

class Bluetooth: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    
    var delegate: BluetoothDelegate!
    var serviceUuid: CBUUID!
    var manager: CBCentralManager!
    var peripheral: CBPeripheral?
    
    func start(delegate: BluetoothDelegate, serviceUuid: CBUUID) {
        self.delegate = delegate
        self.serviceUuid = serviceUuid

        let dispatchQueue = DispatchQueue(label: "com.fireflydesign.simplebluetooth.centralmanager")
        manager = CBCentralManager(delegate: self, queue: dispatchQueue)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch manager.state {
        case .unknown:
            break
        case .resetting:
            break
        case .unsupported:
            break
        case .unauthorized:
            break
        case .poweredOff:
            break
        case .poweredOn:
            NSLog("poweredOn")
            manager.scanForPeripherals(withServices: [self.serviceUuid], options: nil)
        }
    }
    
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        NSLog("didDiscover")
        self.peripheral = peripheral
        peripheral.delegate = self
        manager?.connect(peripheral, options: nil)
    }
    
    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        NSLog("didConnect")
        peripheral.discoverServices(nil)
    }
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        NSLog("didDiscoverServices error: \(String(describing: error))")
        guard let services = peripheral.services else {
            return
        }
        for service in services {
            peripheral.discoverCharacteristics(nil, for: service)
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        NSLog("didDiscoverCharacteristicsFor error: \(String(describing: error))")
        guard let characteristics = service.characteristics else {
            return
        }
        for characteristic in characteristics {
            if characteristic.properties.contains(.notify) {
                peripheral.setNotifyValue(true, for: characteristic)
            }
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        NSLog("didUpdateNotificationStateFor error: \(String(describing: error))")
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        NSLog("didUpdateValue: \(String(describing: characteristic.value))")
        let value = characteristic.value
        DispatchQueue.main.async {
            self.delegate.bluetooth(bluetooth: self, characteristic: characteristic, value: value)
        }
    }
    
    func getCharacteristic(uuid: UInt16) -> CBCharacteristic? {
        for service in peripheral?.services ?? [] {
            for characteristic in service.characteristics ?? [] {
                let data = characteristic.uuid.data
                let short = (data[2] << 8) | (data[3])
                if short == uuid {
                    return characteristic
                }
            }
        }
        return nil
    }

}
