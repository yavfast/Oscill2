package com.oscill.obex;

import androidx.annotation.NonNull;

import com.oscill.utils.Log;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.BitSet;

public class BaseOscillController {

    private final static byte[] EMPTY_DATA = new byte[]{};

    private final String TAG = Log.getTag(this.getClass());

    private final ClientSession clientSession;

    public BaseOscillController(@NonNull ClientSession clientSession) {
        this.clientSession = clientSession;
    }

    @NonNull
    public ClientSession getClientSession() {
        return clientSession;
    }

    @NonNull
    public static String bytesToString(@NonNull byte[] data) {
        return new String(data);
    }

    public static int bytesToInt(@NonNull byte[] data) {
        int result = 0;
        int value = 0;
        int power = 0;

        for (int i = (data.length - 1); i >= 0; i--) {
            value = data[i] & 0xFF;
            result |= value << power;
            power += 8;
        }

        return result;
    }

    public static byte[] intToBytes(int value) {
        byte[] b = new byte[4];

        b[0] = (byte)(0xFF & (value >> 24));
        b[1] = (byte)(0xFF & (value >> 16));
        b[2] = (byte)(0xFF & (value >> 8));
        b[3] = (byte)(0xFF & value);

        return b;
    }

    @NonNull
    public static BitSet bytesToBits(@NonNull byte[] data) {
        int len = data.length * 8;
        BitSet res = new BitSet(len);
        for (int idx = 0; idx < len; idx++) {
            res.set(idx, ((data[idx / 8] & (1 << (idx % 8))) != 0));
        }
        return res;
    }

    @NonNull
    public static byte[] bitsToBytes(@NonNull BitSet data) {
        int size = data.size();
        byte[] res = new byte[(size + 7) / 8];
        for (int idx = 0; idx < size; idx++) {
            if (data.get(idx)) {
                res[idx / 8] |= 1 << (idx % 8);
            }
        }
        return res;
    }

    @NonNull
    public byte[] getProperty(@NonNull String property, int propertyType) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(HeaderSet.OSCILL_PROPERTY, property.getBytes());

        return execute(headerSet, propertyType);
    }

    @NonNull
    public byte[] execute(@NonNull HeaderSet headerSet, int propertyType) throws IOException {
        ClientOperation resOp = getClientSession().get(headerSet);
        try {
            int responseCode = resOp.getResponse();

            if (responseCode == ResponseCodes.OBEX_HTTP_OK) {
                HeaderSet receivedHeader = resOp.getReceivedHeader();

                byte[] res = receivedHeader.getHeader(propertyType);
                if (res != null) {
                    return res;
                }
            } else {
                Log.e(TAG, "Operation fail: ", headerSet, "; code: ", responseCode);
            }
        } finally {
            resOp.close();
        }

        return EMPTY_DATA;
    }

    @NonNull
    public byte[] setRegistry(@NonNull String registry, int propertyType, @NonNull byte[] data) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(HeaderSet.OSCILL_REGISTRY, registry.getBytes());
        headerSet.setHeader(propertyType, data);

        return execute(headerSet, propertyType);
    }

}
