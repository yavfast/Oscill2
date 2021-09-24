package com.oscill.utils;

import androidx.annotation.NonNull;

public class DataUtils {

    @NonNull
    public static int[] getIntData1Byte(@NonNull byte[] data, int offset) {
        int size = data.length - offset;
        int[] res = new int[size];

        int idx = 0;
        int dataIdx = offset;
        while (idx < size) {
            res[idx++] = data[dataIdx++] & 0xff;
        }

        return res;
    }

    @NonNull
    public static int[] getIntData2Byte(@NonNull byte[] data, int offset) {
        int size = (data.length - offset) / 2;
        int[] res = new int[size];

        int idx = 0;
        int dataIdx = offset;
        while (idx < size) {
            res[idx++] = ((data[dataIdx++] & 0xff) << 8) | (data[dataIdx++] & 0xff);
        }

        return res;
    }

    @NonNull
    public static int[] getDiffData(@NonNull int[] data) {
        int size = data.length;
        int[] res = new int[size];
        res[0] = 0;

        for (int idx = 1; idx < size; idx++) {
            res[idx] = data[idx] - data[idx - 1];
        }

        return res;
    }

    @NonNull
    public static int[] getAvgFilteredData(@NonNull int[] data, int peekLen) {
        int size = data.length;
        int[] res = new int[size];

        int d1, d2, d3;
        int r12, r23;
        boolean p12, p23;

        for (int idx = 1; idx < size - 1; idx++) {
            d1 = data[idx - 1];
            d2 = data[idx];
            d3 = data[idx + 1];

            r12 = Math.abs(d1 - d2);
            r23 = Math.abs(d2 - d3);

            p12 = r12 < peekLen;
            p23 = r23 < peekLen;

            int dAvg;
            if (p12 && p23) {
                dAvg = (d1 + d2 + d3) / 3;
            } else if (!p12 && !p23){
                dAvg = (d1 + d3) / 2;
            } else if (p12) {
                dAvg = (d1 + d2) / 2;
            } else { // if (p23)
                dAvg = (d2 + d3) / 2;
            }

            res[idx] = dAvg;
        }

        return res;
    }

}
