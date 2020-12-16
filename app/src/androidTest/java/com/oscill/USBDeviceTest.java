package com.oscill;

import android.content.Context;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;

import androidx.annotation.NonNull;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.rule.GrantPermissionRule;

import com.oscill.controller.OscillConfig;
import com.oscill.controller.OscillProperty;
import com.oscill.obex.ClientSession;
import com.oscill.controller.Oscill;
import com.oscill.obex.ResponseCodes;
import com.oscill.usb.UsbObexTransport;
import com.oscill.utils.AppContextWrapper;
import com.oscill.types.BitSet;
import com.oscill.utils.Log;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;

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
        void run(@NonNull Oscill oscill) throws Exception;
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

                        oscill.reset();

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
            } catch (Exception e) {
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

    @Test
    public void testOscillConfig() {
        runTest(oscill -> {
            OscillConfig config = new OscillConfig(oscill);

            OscillProperty<Float> chanelSensitivity = config.getChanelSensitivity();
            Log.i(TAG, "chanelSensitivity range: " + chanelSensitivity.getRealRange());

            for (float testValue = 0f; testValue <= 10.5f; testValue += 0.1f) {
                chanelSensitivity.setRealValue(testValue);
                Log.i(TAG, "set chanelSensitivity: ", testValue, " -> ", chanelSensitivity.getRealValue());
            }

        });
    }

    /**
     * Однократная оцифровка с автозапуском
     * Регистр способа: 0b00000000 (RS)
     * Действие: Oscill ждет синхронизацию заданное регистром TA время.
     * При наступлении условия или при истечении времени - производит однократную оцифровку и возвращает массив выборок.
     * Применение: исследование однократных и периодических сигналов.
     */
    @Test
    public void testSingleSync() {
        runTest(oscill -> {
            oscill.setProcessingType(BitSet.fromBits(0,0,0,0,0,0,0,0)); // RS

//            oscill.setCPUTickLength(1200); // MC

//            oscill.setSpeed(Header.SPEED_115200);

            int maxSamplesDataSize = oscill.getMaxSamplesDataSize();
            Log.i(TAG, "Max samples data size: " + maxSamplesDataSize);
            oscill.setSamplesDataSize(maxSamplesDataSize); // QS

            oscill.setScanDelay(0); // TD
            oscill.setSamplesOffset(10); // TC

            oscill.setDelayMaxSyncAuto(100); // TA
            oscill.setDelayMaxSyncWait(100); // TW

            oscill.setMinSamplingCount(0); // AR
            oscill.setAvgSamplingCount(0); // AP

            oscill.setChanelSyncMode(BitSet.fromBits(0,0,0,0,0,0,0,0)); // T1
            oscill.setChanelHWMode(BitSet.fromBits(0,0,0,0,0,0,0,0)); // O1
            oscill.setChanelSWMode(BitSet.fromBits(0,0,0,0,0,1,0,0)); // M1

            oscill.setChanelSensitivity(20); // V1
            oscill.setChanelOffset(0); // P1
            oscill.setChanelSyncLevel(0); // S1
            oscill.setSyncType(BitSet.fromBits(0,0,0,0,0,0,1,0)); // RT

            oscill.calibration();

            for (int idx = 0; idx < 10; idx++) {
                byte[] data = oscill.getData();
                Log.i(TAG, "Data: " + Arrays.toString(data));
            }
        });
    }

}