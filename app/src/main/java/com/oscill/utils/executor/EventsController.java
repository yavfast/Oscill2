package com.oscill.utils.executor;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.ArrayUtils;
import com.oscill.utils.Log;
import com.oscill.utils.ObjectUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

public class EventsController {

    private static final String TAG = Log.getTag(EventsController.class/*, Log.Level.WARN*/);

    private static class GCHolder {
        private EventHolder eventHolder;

        GCHolder(@NonNull EventHolder eventHolder) {
            this.eventHolder = eventHolder;
        }

        @Override
        protected void finalize() throws Throwable {
            eventHolder.release();
            unregister(eventHolder);
            super.finalize();
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            GCHolder gcHolder = (GCHolder) o;
            return ObjectUtils.equals(eventHolder, gcHolder.eventHolder);
        }

        @Override
        public int hashCode() {
            return eventHolder.hashCode();
        }
    }

    private static class EventsList extends CopyOnWriteArrayList<EventHolder> {
    }

    private static class GCHolderList extends CopyOnWriteArrayList<GCHolder> {
    }

    private static final Map<Class<? extends IBroadcastEvent>, EventsList> eventsMap = new ConcurrentHashMap<>();

    private static final WeakHashMap<Object, GCHolderList> holdersMap = new WeakHashMap<>();

    @Nullable
    private static List<EventHolder> getHolderList(@NonNull Object holder) {
        synchronized (holdersMap) {
            GCHolderList gcHolderList = holdersMap.get(holder);
            if (!ArrayUtils.isEmpty(gcHolderList)) {
                List<EventHolder> eventsList = new ArrayList<>(gcHolderList.size());
                for (GCHolder gcHolder : gcHolderList) {
                    eventsList.add(gcHolder.eventHolder);
                }
                return eventsList;
            }
        }

        return null;
    }

    private static GCHolderList getOrCreateHolderList(@NonNull Object holder) {
        synchronized (holdersMap) {
            GCHolderList res = holdersMap.get(holder);
            if (res == null) {
                res = new GCHolderList();
                holdersMap.put(holder, res);
            }
            return res;
        }
    }

    @Nullable
    private static EventsList getEventsList(@NonNull Class<? extends IBroadcastEvent> clazz) {
        synchronized (eventsMap) {
            return eventsMap.get(clazz);
        }
    }

    @NonNull
    private static EventsList getOrCreateEventsList(@NonNull Class<? extends IBroadcastEvent> clazz) {
        synchronized (eventsMap) {
            EventsList res = eventsMap.get(clazz);
            if (res == null) {
                res = new EventsList();
                eventsMap.put(clazz, res);
            }
            return res;
        }
    }

    @NonNull
    private static <E extends IBroadcastEvent> EventHolder<E> onReceiveEvent(@Nullable Object holder, @NonNull Class<E> clazz, @NonNull ObjRunnable<E> onReceive, boolean runInBackground) {
        EventHolder<E> eventHolder = createEvent(holder, clazz, onReceive, runInBackground);

        if (holder == null || runInBackground) {
            eventHolder.resume();
        }

        register(eventHolder);

        return eventHolder;
    }

    @NonNull
    public static <E extends IBroadcastEvent> EventHolder<E> createEvent(@Nullable Object holder, @NonNull Class<E> clazz, @NonNull ObjRunnable<E> onReceive, boolean runInBackground) {
        EventHolder<E> eventHolder = new EventHolder<>(holder, clazz, onReceive, runInBackground);
        Log.d(TAG, "Create: ", eventHolder);
        return eventHolder;
    }

    @SuppressWarnings("unchecked")
    public static void register(@NonNull EventHolder eventHolder) {
        Executor.runInTaskQueue(() -> {
            if (getOrCreateEventsList(eventHolder.getEventClass()).addIfAbsent(eventHolder)) {
                Executor.doIfExists(eventHolder.getHolder(), holder -> getOrCreateHolderList(holder).add(new GCHolder(eventHolder)));
            } else {
                Log.w(TAG, "Already registered: ", eventHolder);
            }
        });
    }

    public static void register(@NonNull EventHolder... eventHolders) {
        for (EventHolder holder : eventHolders) {
            register(holder);
        }
    }

    @SuppressWarnings("unchecked")
    public static void unregister(@NonNull EventHolder eventHolder) {
        Executor.runInTaskQueue(() -> {
            EventsList receivers = getEventsList(eventHolder.getEventClass());
            if (receivers != null) {
                receivers.remove(eventHolder);
            }
        });
    }

    public static void unregister(@NonNull EventHolder... eventHolders) {
        for (EventHolder holder : eventHolders) {
            unregister(holder);
        }
    }

    public static <E extends IBroadcastEvent> void unregisterByClass(@NonNull Object holder, @NonNull Class<E> clazz) {
        Executor.runInTaskQueue(() -> {
            Log.i(TAG, "Unregister event: ", clazz, "; holder: ", holder);
            EventsList receivers = getEventsList(clazz);
            if (receivers != null && !receivers.isEmpty()) {
                List<EventHolder> removeList = new ArrayList<>(8);

                for (EventHolder eventHolder : receivers) {
                    if (eventHolder.getHolder() == holder) {
                        removeList.add(eventHolder);
                    }
                }

                for (EventHolder eventHolder : removeList) {
                    eventHolder.release();
                    receivers.remove(eventHolder);
                }
            }
        });
    }

    public static <E extends IBroadcastEvent> void unregisterByClass(@NonNull Object holder, @NonNull Class<E>... clazzes) {
        for (Class<E> clazz : clazzes) {
            unregisterByClass(holder, clazz);
        }
    }

    public static void sendEvent(@NonNull IBroadcastEvent event) {
        sendEvent(event, 0L);
    }

    public static void sendEvent(@NonNull IBroadcastEvent event, long delay) {
        Executor.runInTaskQueue(() -> {
            Log.i(TAG, "Send event: ", event);

            Class<? extends IBroadcastEvent> clazz = event.getClass();
            EventsList eventsList = getEventsList(clazz);
            if (eventsList != null) {
                for (EventHolder eventHolder : eventsList) {
                    eventHolder.execute(event);
                }
            }
        }, delay);
    }

    public static <E extends IBroadcastEvent> EventHolder<E> onReceiveEvent(@Nullable Object holder, @NonNull Class<E> clazz, @NonNull ObjRunnable<E> onReceive) {
        return onReceiveEvent(holder, clazz, onReceive, false);
    }

    public static <E extends IBroadcastEvent> EventHolder<E> onReceiveEventAsync(@Nullable Object holder, @NonNull Class<E> clazz, @NonNull ObjRunnable<E> onReceive) {
        return onReceiveEvent(holder, clazz, onReceive, true);
    }

    public static <E extends IBroadcastEvent> EventHolder<E> onReceiveEventAsync(@NonNull Class<E> clazz, @NonNull ObjRunnable<E> onReceive) {
        return onReceiveEvent(null, clazz, onReceive, true);
    }

    public static void resumeEventsByHolder(@NonNull Object holder) {
        Executor.runInTaskQueue(() -> Executor.doIfExists(getHolderList(holder), events -> {
            for (EventHolder event : events) {
                event.resume();
            }
        }));
    }

    public static void pauseEventsByHolder(@NonNull Object holder) {
        Executor.runInTaskQueue(() -> Executor.doIfExists(getHolderList(holder), events -> {
            for (EventHolder event : events) {
                event.pause();
            }
        }));
    }

    public static void resumeEvents(@NonNull EventHolder... events) {
        for (EventHolder event : events) {
            Executor.doIfExists(event, EventHolder::resume);
        }
    }

    public static void pauseEvents(@NonNull EventHolder... events) {
        for (EventHolder event : events) {
            Executor.doIfExists(event, EventHolder::pause);
        }
    }

    public static void unregisterHolder(@NonNull Object holder) {
        Executor.runInTaskQueue(() -> {
            Log.d(TAG, "Unregister holder: ", holder.getClass().getName());

            synchronized (holdersMap) {
                holdersMap.remove(holder);
            }
        });
    }

}
