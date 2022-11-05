package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.io.BufferedReader;
import java.io.Closeable;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.Charset;

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

    @NonNull
    public static String readFileToString(@NonNull File file, @NonNull Charset charset) {
        try {
            try (InputStream stream = new FileInputStream(file)) {
                try (Reader reader = new BufferedReader(new InputStreamReader(stream, charset))) {
                    StringBuilder builder = new StringBuilder((int) file.length());
                    char[] buffer = new char[8192];
                    int read;
                    while ((read = reader.read(buffer, 0, buffer.length)) > 0) {
                        builder.append(buffer, 0, read);
                    }
                    return builder.toString();
                }
            }
        } catch (IOException e) {
            Log.e(TAG, e);
        }

        return StringUtils.EMPTY;
    }

    public static boolean writeStringToFile(@NonNull File file, @NonNull String str) {
        try {
            if (!file.exists()) {
                if (!file.createNewFile()) {
                    throw new IOException("Create file fail: " + file.getPath());
                }
            }
            try (FileWriter writer = new FileWriter(file, false)) {
                writer.write(str);
                writer.flush();
            }
            return true;
        } catch (IOException e) {
            Log.e(TAG, e);
        }
        return false;
    }

}
