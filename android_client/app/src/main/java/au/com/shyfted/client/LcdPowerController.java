package au.com.shyfted.client;

import android.app.Activity;
import android.graphics.Color;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;

final class LcdPowerController {
    private final Activity activity;
    private final FrameLayout root;
    private final View blankView;
    private boolean lcdOff;
    private float previousScreenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;

    LcdPowerController(Activity activity, FrameLayout root) {
        this.activity = activity;
        this.root = root;
        blankView = new View(activity);
        blankView.setBackgroundColor(Color.BLACK);
        blankView.setVisibility(View.GONE);
        blankView.setClickable(false);
        blankView.setFocusable(false);
        root.addView(blankView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
    }

    boolean isLcdOff() {
        return lcdOff;
    }

    void requestLcdOff(String reason) {
        if (!runOnUiThreadIfNeeded(() -> requestLcdOff(reason))) {
            return;
        }

        if (lcdOff) {
            return;
        }

        try {
            Window window = activity.getWindow();
            WindowManager.LayoutParams params = window.getAttributes();
            previousScreenBrightness = params.screenBrightness;
            params.screenBrightness = 0.0f;
            window.setAttributes(params);
            blankView.bringToFront();
            blankView.setVisibility(View.VISIBLE);
            lcdOff = true;
            Log.i(ShyftedDeviceClient.TAG, "LCD off requested"
                    + " reason=" + reason
                    + " mechanism=window_brightness_zero_black_overlay"
                    + " previous_screen_brightness=" + previousScreenBrightness
                    + " elapsed_ms=" + SystemClock.elapsedRealtime());
        } catch (RuntimeException e) {
            Log.w(ShyftedDeviceClient.TAG, "LCD off request failed reason=" + reason, e);
        }
    }

    void restoreLcd(String reason, long eventElapsedMs) {
        if (!runOnUiThreadIfNeeded(() -> restoreLcd(reason, eventElapsedMs))) {
            return;
        }

        if (!lcdOff) {
            return;
        }

        try {
            blankView.setVisibility(View.GONE);
            Window window = activity.getWindow();
            WindowManager.LayoutParams params = window.getAttributes();
            params.screenBrightness = previousScreenBrightness;
            window.setAttributes(params);
            lcdOff = false;
            long now = SystemClock.elapsedRealtime();
            Log.i(ShyftedDeviceClient.TAG, "LCD restored"
                    + " reason=" + reason
                    + " mechanism=window_brightness_restore_black_overlay_hidden"
                    + " wake_latency_ms=" + Math.max(0L, now - eventElapsedMs)
                    + " restored_screen_brightness=" + previousScreenBrightness
                    + " elapsed_ms=" + now);
        } catch (RuntimeException e) {
            Log.w(ShyftedDeviceClient.TAG, "LCD restore failed reason=" + reason, e);
        }
    }

    private boolean runOnUiThreadIfNeeded(Runnable runnable) {
        if (Thread.currentThread() == activity.getMainLooper().getThread()) {
            return true;
        }
        activity.runOnUiThread(runnable);
        return false;
    }
}
