import { configureStore, Tuple } from '@reduxjs/toolkit';
import { setAutoFreeze } from 'immer';

// Disable Immer's auto-freeze so ezbids objects can be mutated in-place
// (ported from Vue/Vuex which allowed direct state mutation)
setAutoFreeze(false);
import sessionReducer from './slices/sessionSlice';
import ezbidsReducer from './slices/ezbidsSlice';
import eventsReducer from './slices/eventsSlice';
import pageReducer from './slices/pageSlice';

export const store = configureStore({
    reducer: {
        session: sessionReducer,
        ezbids: ezbidsReducer,
        events: eventsReducer,
        page: pageReducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: false, // ezbids state contains complex nested objects
            immutableCheck: false, // ezbids objects are mutated in-place by mapObjects (ported from Vue)
        }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
