package com.oscill.usb;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbManager;
import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.obex.ObexTransport;
import com.oscill.types.SuspendValue;
import com.oscill.utils.AppContextWrapper;
import com.oscill.utils.ArrayUtils;
import com.oscill.utils.ConvertUtils;
import com.oscill.utils.IOUtils;
import com.oscill.utils.Log;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.List;

import usbserial.driver.Cp21xxSerialDriver;
import usbserial.driver.ProbeTable;
import usbserial.driver.UsbId;
import usbserial.driver.UsbSerialDriver;
import usbserial.driver.UsbSerialPort;
import usbserial.driver.UsbSerialProber;

import static com.oscill.usb.UsbReceiver.ACTION_USB_PERMISSION;

public class UsbObexTransport implements ObexTransport {

    private static final String TAG = Log.getTag(UsbObexTransport.class);

    private final SuspendValue<UsbSerialProber> oscillProber = new SuspendValue<>(() -> {
        ProbeTable oscillProbeTable = new ProbeTable();
        oscillProbeTable.addProduct(UsbId.VENDOR_SILABS, 0x840E, Cp21xxSerialDriver.class);
        return new UsbSerialProber(oscillProbeTable);
    });

    private final SuspendValue<UsbSerialDriver> usbDriver = new SuspendValue<>(() -> {
        List<UsbSerialDriver> usbDrivers = getOscillProber().findAllDrivers(getUsbManager());
        if (ArrayUtils.isNotEmpty(usbDrivers)) {
            return usbDrivers.get(0);
        }
        return null;
    });

    @NonNull
    private UsbSerialProber getOscillProber() {
        return oscillProber.get();
    }

    @Nullable
    private UsbSerialDriver getUsbDriver() {
        return usbDriver.get();
    }

    @NonNull
    private UsbSerialDriver getUsbDriverOrThrow() throws IOException {
        UsbSerialDriver usbSerialDriver = usbDriver.get();
        if (usbSerialDriver == null) {
            throw new IOException("USB driver not found");
        }
        return usbSerialDriver;
    }

    private UsbManager getUsbManager() {
        return AppContextWrapper.getSystemService(UsbManager.class);
    }

    @Override
    public void create() throws IOException {
        UsbSerialDriver usbDriver = getUsbDriverOrThrow();
        Log.i(TAG, "Use USB driver: ", usbDriver);
    }

    @Override
    public boolean isDeviceAvailable() {
        return getUsbDriver() != null;
    }

    @Override
    public boolean hasPermissions() {
        UsbSerialDriver usbDriver = getUsbDriver();
        return usbDriver != null && getUsbManager().hasPermission(usbDriver.getDevice());
    }

    @Override
    public void listen() throws IOException {

    }

    @Override
    public void close() throws IOException {
        if (usbDriver.hasValue()) {
            disconnect();
            usbDriver.reset();
        }
    }

    private final SuspendValue<UsbDeviceConnection> usbConnection = new SuspendValue<>(() -> {
        UsbSerialDriver usbDriver = getUsbDriver();
        if (usbDriver != null) {
            UsbDevice usbDevice = usbDriver.getDevice();
            UsbManager usbManager = getUsbManager();
            if (usbManager.hasPermission(usbDevice)) {
                return usbManager.openDevice(usbDevice);
            }
        }
        return null;
    });

    @Nullable
    private UsbDeviceConnection getUsbConnection() {
        return usbConnection.get();
    }

    private final SuspendValue<UsbSerialPort> usbPort = new SuspendValue<>(this::openUsbPort);

    @Nullable
    private UsbSerialPort openUsbPort() {
        UsbSerialDriver usbDriver = getUsbDriver();
        if (usbDriver != null) {
            UsbDeviceConnection connection = getUsbConnection();
            if (connection != null) {
                List<UsbSerialPort> ports = usbDriver.getPorts();
                for (UsbSerialPort port : ports) {
                    try {
                        port.open(connection);
                        // 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
                        port.setParameters(115200, UsbSerialPort.DATABITS_8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE);
                        Log.i(TAG, "Open port: ", port);
                        return port;
                    } catch (IOException e) {
                        Log.e(TAG, e);
                    }
                }
            }
        }
        return null;
    }

    @Nullable
    private UsbSerialPort getUsbPort() {
        return usbPort.get();
    }

    @Override
    public void connect() throws IOException {
        getUsbDriverOrThrow();

        if (hasPermissions()) {
            Log.i(TAG, "Connect");
            UsbDeviceConnection connection = getUsbConnection();
            if (connection != null) {
                if (getUsbPort() != null) {
                    Log.i(TAG, "USB connection successful");
                }
            } else {
                throw new IOException("Open connection fail");
            }
        } else {
            throw new IOException("No USB access permissions");
        }
    }

    @Override
    public void requestPermissions() {
        UsbSerialDriver usbDriver = getUsbDriver();
        if (usbDriver != null) {
            Log.i(TAG, "Request USB permissions");
            Context appContext = AppContextWrapper.getAppContext();
            appContext.registerReceiver(new UsbReceiver(), new IntentFilter(ACTION_USB_PERMISSION));
            PendingIntent intent = PendingIntent.getBroadcast(appContext, 0, new Intent(ACTION_USB_PERMISSION), 0);
            getUsbManager().requestPermission(usbDriver.getDevice(), intent);
        }
    }

    @Override
    public void disconnect() throws IOException {
        if (usbConnection.hasValue()) {
            Log.i(TAG, "Disconnect");
            usbPort.reset(IOUtils::close);
            usbConnection.reset(UsbDeviceConnection::close);
        }
    }

    private class UsbInputStream extends ByteArrayInputStream {

        private final byte[] readBuf = new byte[4096];

        UsbInputStream () {
            this(new byte[getMaxReceivePacketSize()]);
        }

        UsbInputStream(byte[] buf) {
            super(buf);
            count = 0;
        }

        private boolean readPacket(int readDataLen) {
            if (readDataLen > available()) {
                UsbSerialPort usbPort = getUsbPort();
                if (usbPort == null) {
                    return false;
                }

                try {
                    while (readDataLen > available()) {
                        int res = usbPort.read(readBuf, 200);

                        if (res > 0) {
                            System.arraycopy(readBuf, 0, buf, count, res);
                            count += res;

                        } else if (res == 0) {
                            Log.d(TAG, "WAIT DATA");
                            SystemClock.sleep(10L);

                        } else {
                            if (count > 0) {
                                Log.w(TAG, "EOF: ", res);
                                break;
                            } else {
                                // TODO: Maybe internal restart device
                                Log.w(TAG, "WAIT DATA: ", res);
                                SystemClock.sleep(50L);
                            }
                        }
                    }

                    return readDataLen <= available();

                } catch (IOException e) {
                    Log.e(TAG, "Read USB data error: ", e.getMessage());
                    return false;
                }
            }

            return true;
        }

        @Override
        public int read() {
            if (readPacket(1)) {
                return super.read();
            }
            return -1;
        }

        @Override
        public int read(@NonNull byte[] dest) {
            if (readPacket(dest.length)) {
                return super.read(dest, 0, dest.length);
            }
            return 0;
        }

        @Override
        public int read(@NonNull byte[] dest, int off, int len) {
            if (readPacket(len)) {
                return super.read(dest, off, len);
            }
            return 0;
        }

        @Override
        public void reset() {
            dumpBuf();
            pos = 0;
            count = 0;
        }

        public void dumpBuf() {
            if (count > 0) {
                Log.i(TAG, "Read: [", count, "]", ConvertUtils.bytesToHexStr(buf, count));
            }
        }
    }

    private final SuspendValue<InputStream> usbInputStream = new SuspendValue<>(UsbInputStream::new);

    @Override
    public InputStream openInputStream() throws IOException {
        return usbInputStream.get();
    }

    private class UsbOutputStream extends ByteArrayOutputStream {
        UsbOutputStream() {
            super(getMaxTransmitPacketSize());
        }

        @Override
        public void flush() throws IOException {
            UsbSerialPort usbPort = getUsbPort();
            if (usbPort != null) {
                byte[] out = toByteArray();
                Log.i(TAG, "Write: ", ConvertUtils.bytesToHexStr(out, out.length));
                usbPort.write(out, 100);
            }
            reset();
        }
    }

    private final SuspendValue<OutputStream> usbOutputStream = new SuspendValue<>(UsbOutputStream::new);

    @Override
    public OutputStream openOutputStream() throws IOException {
        return usbOutputStream.get();
    }

    @Override
    public DataInputStream openDataInputStream() throws IOException {
        return null;
    }

    @Override
    public DataOutputStream openDataOutputStream() throws IOException {
        return null;
    }

    @Override
    public int getMaxTransmitPacketSize() {
        return 256;
    }

    @Override
    public int getMaxReceivePacketSize() {
        return 4 * 1024;
    }

}
