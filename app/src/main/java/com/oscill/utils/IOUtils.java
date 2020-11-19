package com.oscill.utils;

import androidx.annotation.Nullable;

import java.io.Closeable;
import java.io.IOException;

public class IOUtils {

    private static final String TAG = Log.getTag(IOUtils.class);

    public static void close(@Nullable Closeable closeable) {
        if (closeable != null) {
            try {
                closeable.close();
            } catch (IOException e) {
                Log.d(TAG, e);
            }
        }
    }

}
