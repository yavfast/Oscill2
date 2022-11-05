package com.oscill.controller;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.oscill.controller.settings.OscillSettings;
import com.oscill.types.SuspendValue;
import com.oscill.utils.AppContextWrapper;
import com.oscill.utils.IOUtils;
import com.oscill.utils.Log;
import com.oscill.utils.StringUtils;

import java.io.File;
import java.nio.charset.Charset;

public class OscillPrefs {

    private static final String TAG = Log.getTag(OscillPrefs.class);

    private static final String LAST_SETTINGS_NAME = "last_settings.json";

    private final static SuspendValue<Gson> gson = new SuspendValue<>(() ->
            new GsonBuilder()
                    .setPrettyPrinting()
                    .create()
    );


    @NonNull
    private static File getSettingsDir() {
        return AppContextWrapper.getAppContext().getCacheDir();
    }

    @Nullable
    public static OscillSettings loadLastSettings() {
        return loadSettings(LAST_SETTINGS_NAME);
    }

    @Nullable
    public static OscillSettings loadSettings(@NonNull String settingsName) {
        if (StringUtils.isEmpty(settingsName)) {
            Log.w(TAG, "Settings name is empty");
            return null;
        }

        File settingsFile = new File(getSettingsDir(), settingsName);
        if (!settingsFile.exists()) {
            Log.w(TAG, "Settings file not exists: ", settingsFile);
            return null;
        }

        String json = IOUtils.readFileToString(settingsFile, Charset.defaultCharset());
        if (StringUtils.isEmpty(json)) {
            Log.w(TAG, "Settings file read fail: ", settingsFile);
            return null;
        }

        return gson.get().fromJson(json, OscillSettings.class);
    }

    public static void saveSettings(@NonNull OscillSettings settings) {
        saveSettings(settings, LAST_SETTINGS_NAME);
    }

    public static void saveSettings(@NonNull OscillSettings settings, @NonNull String settingsName) {
        String json = gson.get().toJson(settings);

        File settingsFile = new File(getSettingsDir(), settingsName);
        IOUtils.writeStringToFile(settingsFile, json);
    }
}
