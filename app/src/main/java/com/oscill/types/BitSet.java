package com.oscill.types;

import androidx.annotation.NonNull;

public class BitSet {

    private static final byte BIT_SET = 1;
    private static final byte BIT_CLEAR = 0;

    private byte[] bits;

    public BitSet(int nbits) {
        super();
        initBits(nbits);
    }

    public static BitSet fromBits(@NonNull int... bits) {
        int len = bits.length;
        BitSet res = new BitSet(len);
        for (int idx = 0; idx < len; idx++) {
            res.set(idx, bits[idx] != 0);
        }
        return res;
    }

    @NonNull
    public static BitSet fromBytes(@NonNull byte[] data) {
        int len = data.length * 8;
        BitSet res = new BitSet(len);
        for (int idx = 0; idx < len; idx++) {
            res.set(idx, ((data[idx / 8] & (1 << (idx % 8))) != 0));
        }
        return res;
    }

    private void initBits(int nbits) {
        if (bits != null && bits.length >= nbits) {
            return;
        }

        byte[] data = new byte[nbits];

        if (bits != null) {
            System.arraycopy(bits, 0, data, 0, bits.length);
        }

        bits = data;
    }

    public void set(int bitIdx, boolean value) {
        bits[bitIdx] = value ? BIT_SET : BIT_CLEAR;
    }

    public boolean get(int bitIdx) {
        return bits[bitIdx] != BIT_CLEAR;
    }

    public int size() {
        return bits.length;
    }

    public byte[] toBytes() {
        int size = bits.length;
        byte[] res = new byte[(size + 7) / 8];
        for (int idx = 0; idx < size; idx++) {
            if (get(idx)) {
                res[idx / 8] |= 1 << (idx % 8);
            }
        }
        return res;
    }

    @NonNull
    @Override
    public String toString() {
        int size = bits.length;
        StringBuilder sb = new StringBuilder(size + 2);
        sb.append('{');
        for (int idx = 0; idx < size; idx++) {
            sb.append(get(idx) ? '1' : '0');
        }
        sb.append('}');
        return sb.toString();
    }
}
