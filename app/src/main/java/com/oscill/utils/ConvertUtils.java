package com.oscill.utils;

import androidx.annotation.NonNull;

public class ConvertUtils {

    @NonNull
    public static String bytesToHexStr(@NonNull byte[] bytes, int length) {
        StringBuilder sb = new StringBuilder(length * 3);
        String hexByte;
        byte b;
        for (int idx = 0; idx < length; idx++) {
            b = bytes[idx];
            hexByte = Integer.toHexString(b & 0xff);
            if (hexByte.length() == 1) {
                sb.append('0');
            }
            sb.append(hexByte).append(' ');
        }
        return sb.toString();
    }

}
