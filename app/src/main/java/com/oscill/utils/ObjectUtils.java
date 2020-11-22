package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.util.Arrays;

public class ObjectUtils {

    @SuppressWarnings("unchecked")
    @Nullable
    public static <T> T cast(@Nullable Object obj) {
        return isEmpty(obj) ? null : (T) obj;
    }

    @SuppressWarnings("unchecked")
    @NonNull
    public static <T> T castOrThrow(@Nullable Object obj) {
        if (!isEmpty(obj)) {
            return (T) obj;
        }
        throw new IllegalArgumentException("Cast null object");
    }

    public static <T> boolean equals(@Nullable T obj1, @Nullable T obj2) {
        return obj1 == obj2 || obj1 != null && obj1.equals(obj2);
    }

    public static <T> boolean isEmpty(@Nullable T obj) {
        return obj == null;
    }

    public static long getHashCode(@NonNull Object... objects) {
        long result = 0L;
        for (Object object : objects) {
            result = result * 31L + (object != null ? object.hashCode() : 0L);
        }
        return Math.abs(result);
    }

    public static int hash(Object... values) {
        return Arrays.hashCode(values);
    }

    @NonNull
    public static <T> T getNonNull(@Nullable T value, @NonNull T defValue) {
        return isEmpty(value) ? defValue : value;
    }
}
