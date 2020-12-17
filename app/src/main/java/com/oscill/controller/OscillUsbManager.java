package com.oscill.controller;

import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;

import androidx.annotation.NonNull;

import com.oscill.obex.ClientSession;
import com.oscill.obex.ResponseCodes;
import com.oscill.usb.OnUsbPermissionResponse;
import com.oscill.usb.UsbObexTransport;
import com.oscill.utils.AppContextWrapper;
import com.oscill.utils.Log;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.ObjRunnable;

import java.util.List;

import usbserial.driver.Cp21xxSerialDriver;
import usbserial.driver.ProbeTable;
import usbserial.driver.UsbId;
import usbserial.driver.UsbSerialDriver;
import usbserial.driver.UsbSerialProber;

public class OscillUsbManager {

    private static final String TAG = Log.getTag(OscillUsbManager.class);

    public static void checkDevice(@NonNull ObjRunnable<UsbDevice> onResult) {
        ProbeTable oscillProbeTable = new ProbeTable();
        oscillProbeTable.addProduct(UsbId.VENDOR_SILABS, 0x840E, Cp21xxSerialDriver.class);

        UsbSerialProber oscillProber = new UsbSerialProber(oscillProbeTable);
        UsbManager manager = AppContextWrapper.getSystemService(UsbManager.class);

        List<UsbSerialDriver> availableDrivers = oscillProber.findAllDrivers(manager);
        for (UsbSerialDriver availableDriver : availableDrivers) {
            UsbDevice device = availableDriver.getDevice();
            Log.i(TAG, device.toString());
            onResult.run(device);
            return;
        }
    }

    public static void connectToDevice(@NonNull ObjRunnable<Oscill> onResult) {
        UsbObexTransport usbObexTransport = new UsbObexTransport();
        if (usbObexTransport.isDeviceAvailable()) {
            EventsController.unregisterHolder(onResult);
            try {
                usbObexTransport.create();
                if (usbObexTransport.hasPermissions()) {
                    usbObexTransport.connect();
                    try {
                        ClientSession session = new ClientSession(usbObexTransport);
                        Oscill oscill = new Oscill(session);

                        oscill.reset();

                        int responseCode = oscill.connect();
                        Log.i(TAG, "Connect result: " + Integer.toHexString(responseCode));

                        if (responseCode == ResponseCodes.OBEX_HTTP_OK) {
                            Log.i(TAG, "Connected");
                            onResult.run(oscill);
                        }
                    } finally {
                        usbObexTransport.disconnect();
                    }
                } else {
                    EventsController.onReceiveEventAsync(onResult, OnUsbPermissionResponse.class, event ->
                            connectToDevice(onResult)
                    );
                    usbObexTransport.requestPermissions();
                }
            } catch (Exception e) {
                Log.e(TAG, e);
            }

        } else {
            Log.w(TAG, "Usb device not Available");
        }
    }

}
