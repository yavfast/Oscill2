package com.oscill;

import android.content.Context;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.rule.GrantPermissionRule;

import com.oscill.obex.Oscill;
import com.oscill.obex.ResponseCodes;
import com.oscill.usb.UsbObexTransport;
import com.oscill.utils.AppContextWrapper;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;
import java.util.List;

import com.oscill.obex.ClientSession;
import com.oscill.obex.HeaderSet;

import usbserial.driver.Cp21xxSerialDriver;
import usbserial.driver.ProbeTable;
import usbserial.driver.UsbId;
import usbserial.driver.UsbSerialDriver;
import usbserial.driver.UsbSerialProber;

/**
 * Instrumented test, which will execute on an Android device.
 *
 * @see <a href="http://d.android.com/tools/testing">Testing documentation</a>
 */
@RunWith(AndroidJUnit4.class)
public class USBDeviceTest {

    private static final String TAG = "USBDeviceTest";

    @Before
    public void init() {
        Context appContext = InstrumentationRegistry.getInstrumentation().getTargetContext();
        AppContextWrapper.setAppContext(appContext);
    }

    @Rule
    public GrantPermissionRule permissionRule =
            GrantPermissionRule.grant("com.android.example.USB_PERMISSION");

    @Test
    public void testDevicesList() {
        Context appContext = InstrumentationRegistry.getInstrumentation().getTargetContext();

        ProbeTable oscillProbeTable = new ProbeTable();
        oscillProbeTable.addProduct(UsbId.VENDOR_SILABS, 0x840E, Cp21xxSerialDriver.class);

        UsbSerialProber oscillProber = new UsbSerialProber(oscillProbeTable);
        UsbManager manager = (UsbManager) appContext.getSystemService(Context.USB_SERVICE);

        List<UsbSerialDriver> availableDrivers = oscillProber.findAllDrivers(manager);
        for (UsbSerialDriver availableDriver : availableDrivers) {
            UsbDevice device = availableDriver.getDevice();
            Log.i(TAG, device.toString());
        }
    }

    public interface OscillTest {
        void run(@NonNull Oscill oscill) throws IOException;
    }

    private void runTest(@NonNull OscillTest test) {
        UsbObexTransport usbObexTransport = new UsbObexTransport();
        if (usbObexTransport.isDeviceAvailable()) {
            try {
                usbObexTransport.create();
                if (usbObexTransport.hasPermissions()) {
                    usbObexTransport.connect();
                    try {
                        ClientSession session = new ClientSession(usbObexTransport);
                        Oscill oscill = new Oscill(session);
                        int responseCode = oscill.connect();
                        Log.i(TAG, "Connect result: " + Integer.toHexString(responseCode));

                        if (responseCode == ResponseCodes.OBEX_HTTP_OK) {
                            Log.i(TAG, "Connected");
                            test.run(oscill);
                        }
                    } finally {
                        usbObexTransport.disconnect();
                    }
                } else {
                    usbObexTransport.requestPermissions();
                }
            } catch (IOException e) {
                Log.e(TAG, e.getMessage(), e);
            }

        } else {
            Log.w(TAG, "Usb device not Available");
        }
    }

    @Test
    public void testUsbObexTransport() {
        runTest(oscill -> {
            Log.i(TAG, "DeviceId: " + oscill.getDeviceId());
            Log.i(TAG, "Device SN: " + oscill.getDeviceSerialNumber());
            Log.i(TAG, "Device HW: " + oscill.getDeviceHardwareVersion());
            Log.i(TAG, "Device SW: " + oscill.getDeviceSoftwareVersion());
        });
    }

    @Test
    public void testProperties() {
        runTest(oscill -> {
            Log.i(TAG, "Def tick: " + oscill.getCPUTickDefLength());
            Log.i(TAG, "Min tick: " + oscill.getCPUTickMinLength());

            Log.i(TAG, "Min sampling period: " + oscill.getSamplingMinPeriod());
            Log.i(TAG, "Min roll sampling period: " + oscill.getRollSamplingMinPeriod());
            Log.i(TAG, "Sampling variants: " + oscill.getSamplingVariants().toString());

            Log.i(TAG, "Min stroboscope sampling period: " + oscill.getStroboscopeMinSamplingPeriod());
            Log.i(TAG, "Max stroboscope sampling period: " + oscill.getStroboscopeMaxSamplingPeriod());

            Log.i(TAG, "Max preload samples: " + oscill.getMaxPreloadSamples());
            Log.i(TAG, "Max samples data size: " + oscill.getMaxSamplesDataSize());
            Log.i(TAG, "Chanel sensitivity min: " + oscill.getChanelSensitivityMin());
            Log.i(TAG, "Chanel sensitivity max: " + oscill.getChanelSensitivityMax());
            Log.i(TAG, "Chanel offset min: " + oscill.getChanelOffsetMin());
            Log.i(TAG, "Chanel offset max: " + oscill.getChanelOffsetMax());
            Log.i(TAG, "Chanel delay: " + oscill.getChanelDelay());
        });
    }

    @Test
    public void testRegistry() {
        runTest(oscill -> {

        });
    }

}