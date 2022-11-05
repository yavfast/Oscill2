package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

public class ConvertUtils {

    private static final String TAG = Log.getTag(ConvertUtils.class);

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

    @NonNull
    public static <V extends Number> V convertDoubleTo(@NonNull Double value, @NonNull Class<?> classType) {
        if (classType == Double.class) {
            return (V)value;
        }
        if (classType == Long.class) {
            return (V)Long.valueOf(value.longValue());
        }
        if (classType == Integer.class) {
            return (V)Integer.valueOf(value.intValue());
        }
        if (classType == Float.class) {
            return (V)Float.valueOf(value.floatValue());
        }
        return (V)value;
    }

    @NonNull
    public static <V extends Number> V convertStrTo(@NonNull String str, @NonNull Class<?> classType) {
        return convertDoubleTo(Double.valueOf(str), classType);
    }

    @NonNull
    private static <E extends Enum<?>> E[] getEnumValues(@NonNull Class<E> enumClass) {
        E[] enumValues = enumClass.getEnumConstants();
        return enumValues != null ? enumValues : ArrayUtils.toArray(null, enumClass);
    }

    @Nullable
    public static <E extends Enum<?>> E getEnumByName(@Nullable String name, @NonNull Class<E> enumClass) {
        return getEnumByName(name, enumClass, null);
    }

    public static <E extends Enum<?>> E getEnumByName(@Nullable String name, @NonNull Class<E> enumClass, E defValue) {
        if (name != null) {
            E[] enumValues = getEnumValues(enumClass);
            for (E enumObj : enumValues) {
                if (StringUtils.equalsIgnoreCase(enumObj.toString(), name)) {
                    return enumObj;
                }
            }

            Log.w(TAG, "Not found Enum for name: ", name, "; Enum class: ", enumClass.getName());
        }

        return defValue;
    }
}
