package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.obex.ClientOperation;
import com.oscill.obex.ClientSession;
import com.oscill.obex.Header;
import com.oscill.obex.HeaderSet;
import com.oscill.obex.ResponseCodes;
import com.oscill.utils.Log;

import java.io.IOException;

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

    public static int signed(int value) {
        return (value << 16) >> 16;
    }

    public static int signed(byte value) {
        return (value << 8) >> 8;
    }

    @NonNull
    public static byte[] intToByte(int value) {
        return new byte[]{(byte) (value & 0xFF)};
    }

    @NonNull
    public static byte[] intTo2Bytes(int value) {
        byte[] b = new byte[4];

        b[0] = 0;
        b[1] = 0;
        b[2] = (byte)(0xFF & (value >> 8));
        b[3] = (byte)(0xFF & value);

        return b;
    }

    @NonNull
    public static byte[] intTo4Bytes(int value) {
        byte[] b = new byte[4];

        b[0] = (byte)(0xFF & (value >> 24));
        b[1] = (byte)(0xFF & (value >> 16));
        b[2] = (byte)(0xFF & (value >> 8));
        b[3] = (byte)(0xFF & value);

        return b;
    }

    @NonNull
    public byte[] execute(@NonNull ClientOperation.OperationType operationType, @NonNull HeaderSet headerSet, int propertyType, int beforeResponseDelay) throws IOException {
        ClientOperation resOp = getClientSession().exec(operationType, headerSet);
        resOp.setBeforeResponseDelay(beforeResponseDelay);
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
    public byte[] getProperty(@NonNull String property, int propertyType) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(Header.OSCILL_PROPERTY, property.getBytes());

        return execute(ClientOperation.OperationType.GET, headerSet, propertyType, 0);
    }

    @NonNull
    public byte[] setRegistry(@NonNull String registry, int propertyType, @NonNull byte[] data) throws IOException {
        return setRegistry(registry, propertyType, data, 0);
    }

    @NonNull
    public byte[] setRegistry(@NonNull String registry, int propertyType, @NonNull byte[] data, int beforeResponseDelay) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(Header.OSCILL_REGISTRY, registry.getBytes());
        headerSet.setHeader(propertyType, data);

        return execute(ClientOperation.OperationType.GET, headerSet, propertyType, beforeResponseDelay);
    }

    @NonNull
    public byte[] getRegistry(@NonNull String registry, int propertyType) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(Header.OSCILL_REGISTRY, registry.getBytes());

        return execute(ClientOperation.OperationType.GET, headerSet, propertyType, 0);
    }

    @NonNull
    public byte[] sendCommand(@NonNull String command, int propertyType) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(Header.OSCILL_DATA, command.getBytes());

        return execute(ClientOperation.OperationType.PUT, headerSet, propertyType, 0);
    }

    /**
     * Команда оцифровки
     * Команда инициирует: ожидание синхронизации + предвыборку, оцифровку и возврат данных.
     * Перед этой командой необходимо настроить все регистры, в том числе – регистром способа RS установить требуемый вариант оцифровки.
     * Команда оцифровки передаётся от Comp-а Oscill-у пакетом GET с заголовком 0x72 “D”.
     * В ответ Oscill возвращает Response-пакет Success с заголовком 0x72 = “D” и результатами оцифровки в заголовке 0x49.
     * В режиме бесконечной параллельной оцифровки (ROLL) данные возвращаются Comp-у в Response-пакете Continue.
     * В режиме ждущего запуска, если условие запуска в течение TW выполнено не было,
     * возвращается пакет Success с заголовком 0x72 = “D” и пустым заголовком 0x49.
     */
    @NonNull
    public byte[] getData(int beforeResponseDelay) throws IOException {
        HeaderSet headerSet = new HeaderSet();
        headerSet.setHeader(Header.OSCILL_DATA, "D".getBytes());

        return execute(ClientOperation.OperationType.GET, headerSet, Header.END_OF_BODY, beforeResponseDelay);
    }

}
