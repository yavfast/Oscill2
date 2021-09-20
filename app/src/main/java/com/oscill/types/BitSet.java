package com.oscill.types;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.ObjectUtils;

import java.util.Arrays;

public class BitSet {

    private static final byte BIT_SET = 1;
    private static final byte BIT_CLEAR = 0;

    private byte[] bits; // reverse order

    private BitSet(@NonNull byte... bits) {
        super();
        this.bits = bits;
    }

    public BitSet(int nbits) {
        super();
        initBits(nbits);
    }

    @NonNull
    public BitSet copy() {
        int size = size();
        byte[] copy = new byte[size];
        System.arraycopy(bits, 0, copy, 0, size);
        return new BitSet(copy);
    }

    @NonNull
    public BitSet copy(int fromIdx, int size) {
        byte[] copy = new byte[size];
        System.arraycopy(bits, fromIdx, copy, 0, size);
        return new BitSet(copy);
    }

    @NonNull
    public static BitSet fromBits(@NonNull int... bits) {
        int len = bits.length;
        BitSet res = new BitSet(len);
        for (int idx = 0; idx < len; idx++) {
            res.set(idx, bits[len - idx - 1] != 0);
        }
        return res;
    }

    @NonNull
    public static BitSet fromBytes(@NonNull byte... data) {
        int len = data.length * 8;
        BitSet res = new BitSet(len);
        for (int idx = 0; idx < len; idx++) {
            res.set(idx, ((data[idx / 8] & (1 << (idx % 8))) != 0));
        }
        return res;
    }

    private void initBits(int nbits) {
        if (size() >= nbits) {
            return;
        }

        int size = ((nbits + 7) / 8) * 8;
        byte[] data = new byte[size];

        if (bits != null) {
            System.arraycopy(bits, 0, data, 0, bits.length);
        }

        bits = data;
    }

    @NonNull
    public BitSet set(int bitIdx, boolean value) {
        bits[bitIdx] = value ? BIT_SET : BIT_CLEAR;
        return this;
    }

    public boolean get(int bitIdx) {
        return bits[bitIdx] != BIT_CLEAR;
    }

    public int size() {
        return bits != null ? bits.length : 0;
    }

    public byte[] toBytes() {
        int size = size();
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
        int size = size();
        StringBuilder sb = new StringBuilder(size + 2);
        sb.append('{');
        for (int idx = size - 1; idx >= 0; idx--) {
            sb.append(get(idx) ? '1' : '0');
        }
        sb.append('}');
        return sb.toString();
    }

    @Override
    public boolean equals(@Nullable Object obj) {
        return ObjectUtils.equals(this, obj, (obj1, obj2) ->
                Arrays.equals(obj1.bits, obj2.bits)
        );
    }
}
