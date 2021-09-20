package com.oscill.utils;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.content.res.TypedArray;
import android.graphics.Bitmap;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Point;
import android.graphics.PorterDuff;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.LayerDrawable;
import android.os.Build;
import android.text.Spannable;
import android.text.SpannableString;
import android.text.TextUtils;
import android.text.style.ForegroundColorSpan;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Menu;
import android.view.MenuItem;
import android.view.TouchDelegate;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.view.Window;
import android.view.WindowManager;
import android.widget.AdapterView;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.AttrRes;
import androidx.annotation.ColorInt;
import androidx.annotation.ColorRes;
import androidx.annotation.DimenRes;
import androidx.annotation.DrawableRes;
import androidx.annotation.IdRes;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.StringRes;
import androidx.annotation.StyleableRes;
import androidx.appcompat.content.res.AppCompatResources;
import androidx.appcompat.view.menu.MenuBuilder;
import androidx.appcompat.widget.AppCompatTextView;
import androidx.core.content.res.ResourcesCompat;
import androidx.core.graphics.drawable.DrawableCompat;
import androidx.core.text.PrecomputedTextCompat;
import androidx.core.view.ViewCompat;
import androidx.core.widget.ImageViewCompat;
import androidx.fragment.app.DialogFragment;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentActivity;
import androidx.fragment.app.FragmentManager;

import com.oscill.types.SuspendValue;
import com.oscill.utils.executor.Executor;
import com.oscill.utils.executor.ObjRunnable;

import java.lang.ref.WeakReference;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

public class ViewUtils {

    final private static String TAG = Log.getTag(ViewUtils.class);

    @Nullable
    public static <T extends View> T findViewById(@Nullable ViewGroup viewGroup, @IdRes int viewId) {
        return findViewByIdAndTag(viewGroup, viewId, null, true);
    }

    @NonNull
    public static <T extends View> T findViewByIdOrThrow(@Nullable ViewGroup viewGroup, @IdRes int viewId) {
        return findViewByIdOrThrow(viewGroup, viewId, true);
    }

    @NonNull
    public static <T extends View> T findViewByIdOrThrow(@Nullable ViewGroup viewGroup, @IdRes int viewId, boolean recursive) {
        T res = findViewByIdAndTag(viewGroup, viewId, null, recursive);
        if (res == null) {
            throw new IllegalArgumentException("View not found");
        }
        return res;
    }

    @Nullable
    public static <T extends View> T findViewById(@NonNull Activity activity, @IdRes int viewId) {
        return findViewByIdAndTag((ViewGroup) activity.getWindow().getDecorView(), viewId, null, true);
    }

    @NonNull
    public static <T extends View> T findViewByIdOrThrow(@NonNull Activity activity, @IdRes int viewId) {
        T res = findViewByIdAndTag((ViewGroup) activity.getWindow().getDecorView(), viewId, null, true);
        if (res == null) {
            throw new IllegalArgumentException("View not found");
        }
        return res;
    }

    @Nullable
    public static <T> T findViewByTag(@Nullable ViewGroup viewGroup, @NonNull Class<T> viewClass, @IdRes int tagId, @Nullable Object viewTag) {
        if (viewGroup != null && ResourceUtils.isValidResId(tagId)) {
            List<ViewGroup> childrenViewGroups = new ArrayList<>(8);

            int count = viewGroup.getChildCount();
            for (int idx = 0; idx < count; idx++) {
                View view = viewGroup.getChildAt(idx);
                if (viewClass.isAssignableFrom(view.getClass())) {
                    Object tag = view.getTag(tagId);
                    if (viewTag == null || viewTag.equals(tag)) {
                        return ClassUtils.cast(view);
                    }
                }

                if (view instanceof ViewGroup) {
                    childrenViewGroups.add((ViewGroup) view);
                }
            }

            for (ViewGroup childrenViewGroup : childrenViewGroups) {
                T res = findViewByTag(childrenViewGroup, viewClass, tagId, viewTag);
                if (res != null) {
                    return res;
                }
            }
        }

        return null;
    }

    @Nullable
    public static <T extends View> T findViewByIdAndTag(@Nullable ViewGroup viewGroup, @IdRes int viewId, @Nullable Object viewTag) {
        return findViewByIdAndTag(viewGroup, viewId, viewTag, true);
    }

    @Nullable
    private static <T extends View> T findViewByIdAndTag(@Nullable ViewGroup viewGroup, @IdRes int viewId, @Nullable Object viewTag, boolean recursive) {
        if (viewGroup != null && ResourceUtils.isValidResId(viewId)) {
            List<ViewGroup> childrenViewGroups = new ArrayList<>(8);

            int count = viewGroup.getChildCount();
            for (int idx = 0; idx < count; idx++) {
                View view = viewGroup.getChildAt(idx);
                if (view.getId() == viewId) {
                    Object tag = view.getTag();
                    if (viewTag == null || viewTag.equals(tag)) {
                        return ClassUtils.cast(view);
                    }
                }

                if (recursive && (view instanceof ViewGroup)) {
                    childrenViewGroups.add((ViewGroup) view);
                }
            }

            if (recursive) {
                for (ViewGroup childrenViewGroup : childrenViewGroups) {
                    View res = findViewByIdAndTag(childrenViewGroup, viewId, viewTag, true);
                    if (res != null) {
                        return ClassUtils.cast(res);
                    }
                }
            }
        }

        return null;
    }

    @Nullable
    public static <T extends View> T findViewByClass(@NonNull Activity activity, @NonNull Class<T> clazz) {
        return findViewByClass(getContentView(activity), clazz);
    }

    @SuppressWarnings({"WeakerAccess"})
    @Nullable
    public static <T extends View> T findViewByClass(@NonNull ViewGroup viewGroup, @NonNull Class<T> clazz) {
        View view;
        for (int i = 0; i < viewGroup.getChildCount(); i++) {
            view = viewGroup.getChildAt(i);
            if (clazz.isAssignableFrom(view.getClass())) {
                return ClassUtils.cast(view);
            } else if (view instanceof ViewGroup) {
                view = findViewByClass((ViewGroup) view, clazz);
                if (view != null) {
                    return ClassUtils.cast(view);
                }
            }
        }
        return null;
    }

    @NonNull
    public static ViewGroup getContentView(@NonNull Activity activity) {
        return (ViewGroup) activity.findViewById(android.R.id.content);
    }

    @NonNull
    public static ViewGroup getRootView(@NonNull Activity activity) {
        return (ViewGroup) getContentView(activity).getRootView();
    }

    @NonNull
    public static <T> List<T> findViewsByClass(@NonNull Activity activity, @NonNull Class<T> clazz) {
        return findViewsByClass(getRootView(activity), clazz);
    }

    @NonNull
    @SuppressWarnings({"WeakerAccess"})
    public static <T> List<T> findViewsByClass(@NonNull ViewGroup viewGroup, @NonNull Class<T> clazz) {
        List<T> list = new ArrayList<>();
        View view;
        for (int i = 0; i < viewGroup.getChildCount(); i++) {
            view = viewGroup.getChildAt(i);
            if (clazz.isAssignableFrom(view.getClass())) {
                list.add(ClassUtils.cast(view));
            } else if (view instanceof ViewGroup) {
                list.addAll(findViewsByClass((ViewGroup) view, clazz));
            }
        }
        return list;
    }

    private static final SuspendValue<Integer> splitScreenResId = new SuspendValue<>(() ->
            ResourceUtils.getIdentifier("split_screen", "bool")
    );

    public static boolean splitModeEnabled() {
        return ResourceUtils.getResources().getBoolean(splitScreenResId.get());
    }

    public static void makeActivityCancellableOutside(@NonNull Activity activity) {
        activity.setFinishOnTouchOutside(true);
    }

    public static void setVisible(@Nullable ViewGroup parentView, @IdRes int viewId, boolean visible) {
        setVisible(findViewById(parentView, viewId), visible);
    }

    public static void setVisibleInUI(@Nullable final View view, final boolean visible) {
        Executor.runInUIThread(() -> setVisible(view, visible));
    }

/*
    public static <T extends View> void setVisible(@Nullable ViewBinder<T> viewBinder, boolean visible) {
        if (viewBinder != null) {
            viewBinder.apply(view -> setVisible(view, visible));
        }
    }
*/

    public static void setVisible(@Nullable View view, boolean visible) {
        if (view != null) {
            int value = visible ? View.VISIBLE : View.GONE;
            if (view.getVisibility() != value) {
                view.setVisibility(value);
            }
        }
    }

/*
    public static <T extends View> void setVisibleNoGone(@Nullable ViewBinder<T> viewBinder, boolean visible) {
        if (viewBinder != null) {
            viewBinder.apply(view -> setVisibleNoGone(view, visible));
        }
    }
*/

    public static void setVisibleNoGone(@Nullable View view, boolean visible) {
        if (view != null) {
            int value = visible ? View.VISIBLE : View.INVISIBLE;
            if (view.getVisibility() != value) {
                view.setVisibility(value);
            }
        }
    }

/*
    public static <T extends View> boolean isVisible(@Nullable ViewBinder<T> viewBinder) {
        return viewBinder != null && isVisible(viewBinder.getView());
    }
*/

    public static boolean isVisible(@Nullable View view) {
        return view != null && view.getVisibility() == View.VISIBLE && checkView(view) /*&& BaseActivity.getVisibleActivity() != null*/;
    }

    public static void setEnabled(@Nullable View view, boolean enabled) {
        if (view != null && view.isEnabled() != enabled) {
            view.setEnabled(enabled);
            if (view instanceof ViewGroup) {
                ViewGroup viewGroup = (ViewGroup) view;
                for (int idx = 0; idx < viewGroup.getChildCount(); idx++) {
                    setEnabled(viewGroup.getChildAt(idx), enabled);
                }
            }
        }
    }

/*
    public static <T extends TextView> void setText(@Nullable ViewBinder<T> textView, @Nullable CharSequence text) {
        if (textView != null) {
            textView.apply(view -> setText(view, text));
        }
    }
*/

    public static void setText(@Nullable TextView textView, @Nullable CharSequence text) {
        if (textView != null) {
            if (!TextUtils.equals(textView.getText(), text)) {
                textView.setText(text);
            }
        }
    }

    public static void setLongText(@Nullable AppCompatTextView textView, @Nullable CharSequence text) {
        if (textView != null) {
            if (!TextUtils.equals(textView.getText(), text)) {
                if (TextUtils.isEmpty(text)) {
                    textView.setText(text);
                    return;
                }

                WeakReference<TextView> textViewRef = new WeakReference<>(textView);
                PrecomputedTextCompat.Params params = textView.getTextMetricsParamsCompat();

                Executor.runInBackgroundAsync(() -> {
                    PrecomputedTextCompat precomputedText = PrecomputedTextCompat.create(text, params);
                    Executor.runInUIThreadAsync(() -> {
                        Executor.doIfExistsRef(textViewRef, view -> {
                            view.setText(precomputedText);
                        });
                    });
                });
            }
        }
    }

    public static void setTextBold(@Nullable TextView textView, boolean bold) {
        if (textView != null) {
            textView.setTypeface(null, bold ? Typeface.BOLD : Typeface.NORMAL);
        }
    }

    public static void setText(@Nullable TextView textView, @StringRes int resId) {
        if (ResourceUtils.isValidResId(resId)) {
            setText(textView, ResourceUtils.getString(resId));
        } else {
            setText(textView, null);
        }
    }

    public static void setTextVisible(@Nullable TextView textView, @Nullable CharSequence text) {
        setText(textView, text);
        ViewUtils.setVisible(textView, !TextUtils.isEmpty(text));
    }

/*
    public static <T extends View> void setElevation(@Nullable ViewBinder<T> view, float elevation) {
        if (view != null) {
            view.apply(v -> ViewCompat.setElevation(v, elevation));
        }
    }
*/

    public static <T extends View> void setElevation(@Nullable T view, float elevation) {
        ViewCompat.setElevation(view, elevation);
    }

    public static void setProgress(@Nullable ProgressBar progressBar, int max, int progress) {
        setProgress(progressBar, max, progress, max);
    }

    public static void setProgress(@Nullable ProgressBar progressBar, int max, int progress, int secondaryProgress) {
        if (progressBar != null) {
            boolean changed = false;
            if (max >= 0 && progressBar.getMax() != max) {
                progressBar.setMax(max);
                changed = true;
            }
            if (secondaryProgress >= 0 && progressBar.getSecondaryProgress() != secondaryProgress) {
                progressBar.setSecondaryProgress(secondaryProgress);
                changed = true;
            }
            if (progress >= 0 && progressBar.getProgress() != progress) {
                progressBar.setProgress(progress);
                changed = true;
            }
            if (changed) {
                progressBar.invalidate();
            }
        }
    }

    public static void setProgressDrawable(@Nullable ProgressBar progressBar, @DrawableRes int resId) {
        if (progressBar != null && ResourceUtils.isValidResId(resId)) {
            Drawable drawable = ViewUtils.getDrawable(resId);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                progressBar.setProgressDrawableTiled(drawable);
            } else {
                progressBar.setProgressDrawable(drawable);
            }
        }
    }

    public static void setIndeterminateDrawable(@Nullable ProgressBar progressBar, @DrawableRes int resId) {
        if (progressBar != null && ResourceUtils.isValidResId(resId)) {
            Drawable drawable = ViewUtils.getDrawable(resId);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                progressBar.setIndeterminateDrawableTiled(drawable);
            } else {
                progressBar.setIndeterminateDrawable(drawable);
            }
        }
    }

    public static void setMenuVisible(@NonNull Menu menu, @IdRes int menuId, boolean visible) {
        MenuItem menuItem = menu.findItem(menuId);
        if (menuItem != null) {
            menuItem.setVisible(visible);
        }
    }

    public static void setMenuVisible(@Nullable MenuItem menuItem, boolean visible) {
        if (menuItem != null) {
            menuItem.setVisible(visible);
        }
    }

    public static void setMenuIcon(@NonNull Menu menu, @IdRes int menuId, @DrawableRes int resId) {
        MenuItem menuItem = menu.findItem(menuId);
        if (menuItem != null) {
            Drawable drawable = ViewUtils.getDrawable(resId);
            if (drawable != menuItem.getIcon()) {
                menuItem.setIcon(drawable);
            }
        }
    }

    public static boolean isMenuVisible(@NonNull Menu menu, @IdRes int menuId) {
        MenuItem menuItem = menu.findItem(menuId);
        return (menuItem != null && menuItem.isVisible());
    }

    public static void setMenuEnabled(@NonNull Menu menu, @IdRes int menuId, boolean enabled) {
        MenuItem menuItem = menu.findItem(menuId);
        if (menuItem != null) {
            setMenuEnabled(menuItem, enabled, android.R.color.black, android.R.color.darker_gray);
        }
    }

    public static void setMenuEnabled(@NonNull MenuItem menuItem, boolean enabled, @ColorRes int enabledColor, @ColorRes int disabledColor) {
        boolean changed = enabled != menuItem.isEnabled();
        if (changed) {
            menuItem.setEnabled(enabled);
        }

        CharSequence title = menuItem.getTitle();

        if (changed || !(title instanceof SpannableString)) {
            String titleText = title.toString();
            int color = enabled ? ViewUtils.getColor(enabledColor) : ViewUtils.getColor(disabledColor);

            Spannable spannable = SpannableString.valueOf(titleText);
            spannable.setSpan(new ForegroundColorSpan(color), 0, titleText.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            menuItem.setTitle(spannable);
        }

/*
        Drawable icon = menuItem.getIcon();
        if (icon != null) {
            int alpha = enabled ? 255 : 153; // R.integer.disabled_menu_alpha;
            icon.setAlpha(alpha & 0xFF);
        }
*/
    }

    public static void updateMenu(@NonNull Menu menu, @NonNull ObjRunnable<Menu> updateMenuTask) {
        beginUpdateMenu(menu);
        try {
            updateMenuTask.run(menu);
        } finally {
            endUpdateMenu(menu);
        }
    }

    @SuppressLint("RestrictedApi")
    private static void beginUpdateMenu(@NonNull Menu menu) {
        Executor.doIfCast(menu, MenuBuilder.class, MenuBuilder::stopDispatchingItemsChanged);
    }

    @SuppressLint("RestrictedApi")
    private static void endUpdateMenu(@NonNull Menu menu) {
        Executor.doIfCast(menu, MenuBuilder.class, MenuBuilder::startDispatchingItemsChanged);
    }

    public static void setMenuShowAsAction(@NonNull Menu menu, @IdRes int menuId, int actionEnum) {
        MenuItem menuItem = menu.findItem(menuId);
        if (menuItem != null) {
            menuItem.setShowAsAction(actionEnum);
        }
    }

    public static void setMenuTitle(@NonNull Menu menu, @IdRes int menuId, @StringRes int stringResId) {
        MenuItem menuItem = menu.findItem(menuId);
        if (menuItem != null) {
            menuItem.setTitle(stringResId);
        }
    }

/*
    public static void updateHTMLText(@Nullable TextView view) {
        if (view != null) {
            CharSequence text = view.getText();
            view.setText(ConvertUtils.fromHtml(text));
        }
    }
*/

    public static void setUnderline(@Nullable TextView view) {
        if (view != null) {
            view.setPaintFlags(view.getPaintFlags() | Paint.UNDERLINE_TEXT_FLAG);
        }
    }

    private static boolean isFullscreenMode = false;

    private static int getVisibleFlag(boolean visible) {
        int res;
        if (visible) {
            res = View.SYSTEM_UI_FLAG_VISIBLE;
        } else {
            res = View.SYSTEM_UI_FLAG_LOW_PROFILE
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
                res |= View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_FULLSCREEN;
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
                res |= View.SYSTEM_UI_FLAG_IMMERSIVE
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
            }
        }

        return res;
    }

    private static void setSystemUiVisibility(Context context, boolean visible, View.OnSystemUiVisibilityChangeListener callback) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            if (context instanceof Activity) {
                View decorView = ((Activity) context).getWindow().getDecorView();

                // Этот коллбэк для последующей смены фулскрин режима
                decorView.setOnSystemUiVisibilityChangeListener(callback);

                decorView.setSystemUiVisibility(getVisibleFlag(visible));
            }
        }

        isFullscreenMode = !visible;

        // Этот коллбэк должен вызваться сразу же. Первый коллбэк может и не вызваться.
        if (callback != null) {
            callback.onSystemUiVisibilityChange(getVisibleFlag(visible));
        }
    }

    private static int getSystemUiVisibility(@NonNull Activity activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            View decorView = activity.getWindow().getDecorView();
            return decorView.getSystemUiVisibility();
        } else {
            return getVisibleFlag(!isFullscreenMode);
        }
    }

    public static void setFullScreenMode(@NonNull Activity activity, boolean isFullscreen, @Nullable View.OnSystemUiVisibilityChangeListener callback) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            if (isFullscreen != isFullscreenMode(activity)) {
                setSystemUiVisibility(activity, !isFullscreen, callback);
            }
        } else {
            isFullscreenMode = isFullscreen;
            if (callback != null) {
                callback.onSystemUiVisibilityChange(getVisibleFlag(!isFullscreen));
            }
        }
    }

    public static boolean isFullscreenMode(@NonNull Activity activity) {
        return (getSystemUiVisibility(activity) != 0);
    }

    public static void showToast(@Nullable String message, int duration) {
        if (StringUtils.isNotEmpty(message)) {
            Log.i("Toast", message);
            Executor.runInUIThread(() -> Toast.makeText(AppContextWrapper.getAppContext(), message, duration).show());
        }
    }

    public static void showToast(@Nullable String message) {
        showToast(message, Toast.LENGTH_LONG);
    }

    public static void showToast(@StringRes int resid) {
        showToast(ResourceUtils.getString(resid), Toast.LENGTH_LONG);
    }

    @SuppressWarnings("WeakerAccess")
    public static boolean isLandscapeMode() {
        return ResourceUtils.getResources().getConfiguration().orientation == Configuration.ORIENTATION_LANDSCAPE;
    }

    public static boolean isTabletDevice(@NonNull Context context) {
        return (context.getResources().getConfiguration().screenLayout & Configuration.SCREENLAYOUT_SIZE_MASK) >= Configuration.SCREENLAYOUT_SIZE_LARGE;
    }

    @NonNull
    public static ViewSizes getScreenSizes() {
        WindowManager wm = AppContextWrapper.getSystemService(WindowManager.class);
        DisplayMetrics metrics = new DisplayMetrics();
        wm.getDefaultDisplay().getMetrics(metrics);

        ViewSizes sizes = new ViewSizes();
        sizes.width = metrics.widthPixels;
        sizes.height = metrics.heightPixels;
        return sizes;
    }

    public static int dpToPx(int dp) {
        DisplayMetrics displayMetrics = ResourceUtils.getResources().getDisplayMetrics();
        return Math.round(dp * (displayMetrics.densityDpi / (float) DisplayMetrics.DENSITY_DEFAULT));
    }

    public static int pxFromRes(@DimenRes int dimenRes) {
        return ResourceUtils.getResources().getDimensionPixelSize(dimenRes);
    }

    public static class ViewSizes {
        public int width;
        public int height;

        public boolean isEmpty() {
            boolean result = false;
            if (0 >= width || 0 >= height) {
                result = true;
            }
            return result;
        }
    }

    @NonNull
    public static ViewSizes getSizes(@NonNull View view) {
        ViewSizes sizes = new ViewSizes();
        sizes.width = view.getWidth();
        sizes.height = view.getHeight();

        if (sizes.isEmpty()) {
            ViewGroup.LayoutParams params = view.getLayoutParams();
            if (null != params) {
                int widthSpec = View.MeasureSpec.makeMeasureSpec(params.width, View.MeasureSpec.AT_MOST);
                int heightSpec = View.MeasureSpec.makeMeasureSpec(params.height, View.MeasureSpec.AT_MOST);
                view.measure(widthSpec, heightSpec);
            }

            sizes.width = view.getMeasuredWidth();
            sizes.height = view.getMeasuredHeight();
        }

        return sizes;
    }

    public static boolean isViewAttached(@NonNull View view) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            return view.isAttachedToWindow();
        }
        return view.getParent() != null;
    }

    @SuppressWarnings("ConstantConditions")
    @NonNull
    public static Activity getParentActivity(@NonNull View view) {
        Context context = view.getContext();
        while ((context instanceof ContextWrapper) && !(context instanceof Activity)) {
            context = ((ContextWrapper) context).getBaseContext();
        }
        return (Activity) context;
    }

    @SuppressWarnings("WeakerAccess")
    public static boolean hasValidActivity(@NonNull View view) {
        Activity activity = getParentActivity(view);
        return isValidActivity(activity);
    }

    @SuppressWarnings("WeakerAccess")
    public static boolean isValidActivity(@Nullable Activity activity) {
        return activity != null
                && !(activity.isFinishing() || (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1 && activity.isDestroyed()));
    }

    @Nullable
    public static <T> T getParentView(@NonNull View view, @NonNull Class<T> parentClass) {
        ViewParent parent = view.getParent();
        while (parent != null && !ClassUtils.isInstanceOf(parent, parentClass)) {
            parent = parent.getParent();
        }
        return ClassUtils.castOrNull(parent);
    }

    public static void detachView(@NonNull View view) {
        Executor.doIfExists((ViewGroup) view.getParent(), parent -> parent.removeView(view));
    }

    public static void attachView(@NonNull ViewGroup layout, @NonNull View view) {
        ViewGroup parent = (ViewGroup) view.getParent();
        if (parent != null) {
            if (parent != layout) {
                parent.removeView(view);
            } else {
                return;
            }
        }

        layout.addView(view);
    }

    public static void expandTouchArea(@NonNull View parentView, @NonNull View childView,
                                       int extraLeft, int extraRight,
                                       int extraTop, int extraBottom) {
        parentView.post(() -> {
            Rect rect = new Rect();
            childView.getHitRect(rect);
            rect.top -= extraTop;
            rect.left -= extraLeft;
            rect.right += extraRight;
            rect.bottom += extraBottom;
            parentView.setTouchDelegate(new TouchDelegate(rect, childView));
        });
    }

    @NonNull
    public static Point getScreenSize() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1) {
            Point result = new Point();
            WindowManager windowManager = AppContextWrapper.getSystemService(WindowManager.class);
            windowManager.getDefaultDisplay().getRealSize(result);
            return result;
        } else {
            return getDisplayViewSize();
        }
    }

    @SuppressWarnings("WeakerAccess")
    @NonNull
    public static Point getDisplayViewSize() {
        Point result = new Point();
        WindowManager windowManager = AppContextWrapper.getSystemService(WindowManager.class);
        windowManager.getDefaultDisplay().getSize(result);
        return result;
    }

    @NonNull
    public static Point getLocationOnScreen(@NonNull View view) {
        int scrXY[] = new int[2];
        view.getLocationOnScreen(scrXY);
        int resX = scrXY[0];
        int resY = scrXY[1];
        return new Point(resX, resY);
    }

    private static Method mSetLeftTopRightBottomMethod;

    @SuppressLint("SoonBlockedPrivateApi")
    @SuppressWarnings("WeakerAccess")
    public static void setViewBounds(@NonNull View view, int left, int top, int right, int bottom) {
        if (mSetLeftTopRightBottomMethod == null) {
            try {
                mSetLeftTopRightBottomMethod = View.class.getDeclaredMethod("setFrame", int.class, int.class, int.class, int.class);
                mSetLeftTopRightBottomMethod.setAccessible(true);
            } catch (NoSuchMethodException e) {
                Log.e(TAG, e);
            }
        }

        if (mSetLeftTopRightBottomMethod != null) {
            try {
                Log.d(TAG, Log.format("setBounds: %d,%d - %d,%d", left, top, right, bottom));
                mSetLeftTopRightBottomMethod.invoke(view, left, top, right, bottom);
            } catch (Exception e) {
                Log.e(TAG, e);
            }
        }
    }

    public static void setViewToFullscreen(@NonNull View view) {
        Point viewSize = getScreenSize();
        ViewGroup.LayoutParams layoutParams = view.getLayoutParams();
        layoutParams.width = viewSize.x;
        layoutParams.height = viewSize.y;

        Point translateCorrection = getLocationOnScreen(view);
        setViewBounds(view, translateCorrection.x, translateCorrection.y, -translateCorrection.x + viewSize.x, -translateCorrection.y + viewSize.y);
    }

    public static <T> boolean checkUIComponent(@Nullable T component) {
        if (component != null) {
            if (component instanceof Activity) {
                return checkActivity((Activity) component);
            }
            if (component instanceof Fragment) {
                return checkFragment((Fragment) component);
            }
            if (component instanceof View) {
                return checkViewAttached((View) component);
            }
            return true;
        }
        return false;
    }

    public static boolean checkView(@Nullable View view) {
        return view != null && checkActivity(getParentActivity(view));
    }

    public static boolean checkViewAttached(@Nullable View view) {
        return view != null && view.getParent() != null && ViewCompat.isAttachedToWindow(view);
    }

    public static boolean checkActivity(@Nullable Activity activity) {
        return activity != null && !activity.isFinishing() && !isStateSaved(activity) && !isDestroyed(activity);
    }

    public static boolean checkFragment(@Nullable Fragment fragment) {
        return fragment != null && !fragment.isDetached() && !fragment.isRemoving() && checkActivity(fragment.getActivity());
    }

    private static boolean isDestroyed(@NonNull Activity activity) {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1 && activity.isDestroyed();
    }

    private static boolean isStateSaved(@NonNull Activity activity) {
        return activity instanceof FragmentActivity && ((FragmentActivity) activity).getSupportFragmentManager().isStateSaved();
    }

    public static boolean equals(@Nullable View view1, @Nullable View view2) {
        return view1 != null && view1.equals(view2);
    }

    public static void unBindListeners(@Nullable View view) {
        if (view != null) {
            try {
                setOnClickListener(view, null);

                view.setOnLongClickListener(null);
                view.setOnTouchListener(null);
                view.setOnDragListener(null);
                view.setOnFocusChangeListener(null);
                view.setOnGenericMotionListener(null);
                view.setOnSystemUiVisibilityChangeListener(null);

                if (view instanceof ViewGroup && !(view instanceof AdapterView)) {
                    ViewGroup viewGroup = (ViewGroup) view;
                    int viewGroupChildCount = viewGroup.getChildCount();
                    for (int i = 0; i < viewGroupChildCount; i++) {
                        unBindListeners(viewGroup.getChildAt(i));
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, e);
            }

        }
    }

    public static void setOnClickListener(@Nullable View view, @Nullable View.OnClickListener listener) {
        if (view != null && (listener != null || view.hasOnClickListeners())) {
            view.setOnClickListener(listener);
        }
    }

    @SuppressLint("NewApi")
    public static int getSoftButtonsBarHeight(@NonNull Context activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1) {
            if (!isLandscapeMode() && activity instanceof Activity) {
                DisplayMetrics metrics = new DisplayMetrics();
                ((Activity) activity).getWindowManager().getDefaultDisplay().getMetrics(metrics);
                int usableHeight = metrics.heightPixels;
                ((Activity) activity).getWindowManager().getDefaultDisplay().getRealMetrics(metrics);
                int realHeight = metrics.heightPixels;
                if (realHeight > usableHeight) {
                    return realHeight - usableHeight;
                }
            }
        }

        return 0;
    }

/*
    public static void setImageView(@Nullable ViewBinder<ImageView> imageView, @DrawableRes int resId) {
        if (imageView != null) {
            imageView.apply(v -> setImageView(v, resId));
        }
    }
*/

    public static void setImageView(@Nullable ImageView imageView, @DrawableRes int resId) {
        setImageView(imageView, resId, 0);
    }

    @SuppressWarnings("WeakerAccess")
    public static void setImageView(@Nullable ImageView imageView, @DrawableRes int resId, @ColorRes int tintColorResId) {
        if (imageView == null) {
            return;
        }

        if (!ResourceUtils.isValidResId(resId)) {
            setImageView(imageView, null);
            return;
        }

        if (sDrawableCache.contains(resId)) {
            setImageView(imageView, getDrawable(resId, tintColorResId));
        } else {
            Drawable oldDrawable = imageView.getDrawable();
            Executor.runInTaskQueue(() -> {
                Drawable resDrawable = getDrawable(resId, tintColorResId);
                Executor.runInUIThreadAsync(() -> {
                    if (oldDrawable == imageView.getDrawable()) {
                        imageView.setImageDrawable(resDrawable);
                    }
                });
            });
        }
    }

    @SuppressWarnings("WeakerAccess")
    public static void setImageView(@Nullable ImageView imageView, @Nullable Drawable drawable) {
        if (imageView != null) {
            imageView.setImageDrawable(drawable);
        }
    }

    public static void onOrientationChanged() {
        sDrawableCache.evictAll();
        sBitmapCache.evictAll();
        sColorCache.evictAll();
    }

    private static final ValueCache<Integer, Drawable> sDrawableCache = new ValueCache<>(128, resId ->
            AppCompatResources.getDrawable(AppContextWrapper.getAppContext(), resId)
    );

    public static void resetDrawableCache(@DrawableRes int... resIds) {
        for (int resId : resIds) {
            if (ResourceUtils.isValidResId(resId)) {
                sDrawableCache.remove(resId);
            }
        }
    }

    @NonNull
    public static Drawable getDrawable(@DrawableRes int resId, @ColorRes int tintColorResId) {
        Drawable drawable = getDrawable(resId);
        if (ResourceUtils.isValidResId(tintColorResId)) {
            Drawable.ConstantState constantState = drawable.mutate().getConstantState();
            if (constantState != null) {
                int tintColor = getColor(tintColorResId);
                drawable = constantState.newDrawable().mutate();
                DrawableCompat.setTint(drawable, tintColor);
            }
        }
        return drawable;
    }

    @NonNull
    public static Drawable getDrawable(@DrawableRes int resId, @ColorRes int tintColorResId, int paddingPx) {
        Drawable d = getDrawable(resId, tintColorResId);
        if (paddingPx > 0) {
            d = new LayerDrawable(new Drawable[]{d});
            ((LayerDrawable) d).setLayerInset(0, paddingPx, paddingPx, paddingPx, paddingPx);
        }
        return d;
    }

    @NonNull
    public static Drawable getDrawable(@DrawableRes int resId) {
        return sDrawableCache.get(resId);
    }

    private static final ValueCache<Integer, Bitmap> sBitmapCache = new ValueCache<>(64, resId ->
            drawableToBitmap(getDrawable(resId))
    );

    @NonNull
    public static Bitmap getBitmap(@DrawableRes int resId) {
        return sBitmapCache.get(resId);
    }

    private static final ValueCache<Integer, Integer> sColorCache = new ValueCache<>(colorResId ->
            ResourcesCompat.getColor(ResourceUtils.getResources(), colorResId, null)
    );

    public static int getColor(@ColorRes int colorResId) {
        return sColorCache.get(colorResId);
    }

    @Nullable
    public static Drawable getDrawable(@NonNull TypedArray typedArray, @StyleableRes int resId) {
        int drawableId = typedArray.getResourceId(resId, -1);
        return ResourceUtils.isValidResId(drawableId) ? getDrawable(drawableId) : null;
    }

    @NonNull
    public static Bitmap drawableToBitmap(@NonNull Drawable drawable) {
        if (drawable instanceof BitmapDrawable) {
            return ((BitmapDrawable) drawable).getBitmap();
        }

        int width = drawable.getIntrinsicWidth();
        width = width > 0 ? width : 1;
        int height = drawable.getIntrinsicHeight();
        height = height > 0 ? height : 1;

        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);
        drawable.setBounds(0, 0, canvas.getWidth(), canvas.getHeight());
        drawable.draw(canvas);

        return bitmap;
    }

    @Deprecated
    public static Bitmap getColorBitmap(int w, int h, int color) {
        Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        b.eraseColor(color);
        return b;
    }

    @NonNull
    public static Drawable overlayDrawable(@NonNull Drawable background, @NonNull Drawable... overlays) {
        Rect bgRect = background.getBounds();

        int width;
        int height;
        if (bgRect.isEmpty()) {
            width = background.getIntrinsicWidth();
            height = background.getIntrinsicHeight();
        } else {
            width = bgRect.width();
            height = bgRect.height();
        }

        Bitmap result = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(result);

        background.setBounds(0, 0, width, height);
        background.draw(canvas);

        for (Drawable overlay : overlays) {
            Rect bounds = overlay.getBounds();
            if (bounds.isEmpty()) {
                // Draw in center
                int overlayWidth = overlay.getIntrinsicWidth();
                int overlayHeight = overlay.getIntrinsicHeight();

                int left = (width - overlayWidth) / 2;
                int top = (height - overlayHeight) / 2;

                overlay.setBounds(left, top, left + overlayWidth, top + overlayHeight);
            }
            overlay.draw(canvas);
        }

        return new BitmapDrawable(ResourceUtils.getResources(), result);
    }

    public static Drawable roundCorners(BitmapDrawable in, int radius) {
        return new BitmapDrawable(ResourceUtils.getResources(), roundCorners(in.getBitmap(), radius));
    }

    public static Bitmap roundCorners(Bitmap in, int radius) {
        Bitmap result = Bitmap.createBitmap(in.getWidth(), in.getHeight(), Bitmap.Config.ARGB_8888);
        BitmapShader shader = new BitmapShader(in, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP);
        Paint paint = new Paint();
        paint.setAntiAlias(true);
        paint.setShader(shader);
        RectF rect = new RectF(0, 0, result.getWidth(), result.getHeight());
        Canvas newCanvas = new Canvas(result);
        newCanvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR);
        newCanvas.drawRoundRect(rect, radius, radius, paint);
        newCanvas.setBitmap(null);
        return result;
    }

    public static boolean isDialogOpened(@NonNull FragmentManager fragmentManager) {
        List<Fragment> fragments = fragmentManager.getFragments();
        for (Fragment fragment : fragments) {
            if (fragment instanceof DialogFragment) {
                return true;
            }
        }
        return false;
    }

    public static void setMarginTop(@NonNull View view, int marginTop) {
        if (view.getLayoutParams() instanceof ViewGroup.MarginLayoutParams) {
            ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) view.getLayoutParams();
            lp.setMargins(lp.leftMargin, marginTop, lp.rightMargin, lp.bottomMargin);
        }
    }

    public static int getMarginTop(@NonNull View view) {
        if (view.getLayoutParams() instanceof ViewGroup.MarginLayoutParams) {
            ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) view.getLayoutParams();
            return lp.topMargin;
        }
        return 0;
    }

    public static void setMarginBottom(@NonNull View view, int marginBottom) {
        if (view.getLayoutParams() instanceof ViewGroup.MarginLayoutParams) {
            ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) view.getLayoutParams();
            lp.setMargins(lp.leftMargin, lp.topMargin, lp.rightMargin, marginBottom);
        }
    }

    public static int getMarginBottom(@NonNull View view) {
        if (view.getLayoutParams() instanceof ViewGroup.MarginLayoutParams) {
            ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) view.getLayoutParams();
            return lp.bottomMargin;
        }
        return 0;
    }

    public static void setLayoutParams(@NonNull View view, int width, int height) {
        setLayoutParams(view, width, height, true);
    }

    public static void setLayoutParams(@NonNull View view, int width, int height, boolean requestLayout) {
        ViewGroup.LayoutParams layoutParams = view.getLayoutParams();
        if (layoutParams == null) {
            layoutParams = new ViewGroup.LayoutParams(width, height);
            view.setLayoutParams(layoutParams);
        } else {
            if (layoutParams.width != width || layoutParams.height != height) {
                layoutParams.width = width;
                layoutParams.height = height;
                if (requestLayout) {
                    view.requestLayout();
                }
            }
        }
    }

    public static int getStatusBarHeight() {
        int result = 0;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Context context = AppContextWrapper.getAppContext();
            int resourceId = context.getResources().getIdentifier("status_bar_height", "dimen", "android");
            if (resourceId > 0) {
                result = context.getResources().getDimensionPixelSize(resourceId);
            }
        }
        return result;
    }

    public static void setStatusBarColor(@NonNull Activity activity, @ColorInt int color) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = activity.getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(color);
        }
    }

    public static void setTintColor(View view, @ColorInt int colorId) {
        ColorStateList list = ColorStateList.valueOf(colorId);
        if (view instanceof ImageView) {
            ImageViewCompat.setImageTintList((ImageView) view, list);
        } else if (view instanceof TextView) {
            ((TextView) view).setTextColor(list);
        } else {
            ViewCompat.setBackgroundTintList(view, list);
        }
    }

    @ColorInt
    public static int getThemeColorInt(@NonNull Context context, @AttrRes int colorAttr) {
        Integer color = getThemeColor(context, colorAttr);
        return color != null ? color : 0;
    }

    @Nullable
    public static Integer getThemeColor(@NonNull Context context, @AttrRes int colorAttr) {
        final TypedValue value = new TypedValue();
        if (context.getTheme().resolveAttribute(colorAttr, value, true)) {
            return value.data;
        }
        return null;
    }

    @DrawableRes
    public static Integer getThemeDrawableInt(@NonNull Context context, @AttrRes int drawableAttr) {
        Integer id = getThemeDrawableId(context, drawableAttr);
        return id != null ? id : 0;
    }

    @Nullable
    @DrawableRes
    public static Integer getThemeDrawableId(@NonNull Context context, @AttrRes int drawableAttr) {
        final TypedValue value = new TypedValue();
        if (context.getTheme().resolveAttribute(drawableAttr, value, true)) {
            return value.resourceId;
        }
        return null;
    }

    @Nullable
    public static Drawable getThemeDrawable(@NonNull Context context, @AttrRes int drawableAttr) {
        Integer id = getThemeDrawableId(context, drawableAttr);
        return id != null ? getDrawable(id, 0) : null;
    }

    @Nullable
    public static Drawable getAttrDrawable(@NonNull TypedArray attributes, @StyleableRes int index) {
        int resId = attributes.getResourceId(index, 0);
        return resId != 0 ? getDrawable(resId) : null;
    }

    @Nullable
    public static Drawable getAttrDrawable(@NonNull Context context, @NonNull TypedArray attributes, @StyleableRes int index) {
        int resId = attributes.getResourceId(index, 0);
        return resId != 0 ? AppCompatResources.getDrawable(context, resId) : null;
    }


}
