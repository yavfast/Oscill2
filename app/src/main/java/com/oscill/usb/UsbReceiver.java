package com.oscill.usb;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.hardware.usb.UsbManager;

import com.oscill.utils.Log;
import com.oscill.utils.StringUtils;
import com.oscill.utils.executor.EventsController;

class UsbReceiver extends BroadcastReceiver {

    private final static String TAG = Log.getTag(UsbReceiver.class);

    public static final String ACTION_USB_PERMISSION = "com.android.example.USB_PERMISSION";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent != null) {
            if (StringUtils.equals(intent.getAction(), ACTION_USB_PERMISSION)) {
                boolean granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false);
                Log.i(TAG, "USB permission granted: ", granted);
                EventsController.sendEvent(new OnUsbPermissionResponse());
            }
        }
    }
}
