import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type PageName =
    | 'upload'
    | 'description'
    | 'subject'
    | 'seriespage'
    | 'event'
    | 'object'
    | 'deface'
    | 'participant'
    | 'finalize'
    | 'feedback';

interface PageState {
    current: PageName;
}

const initialState: PageState = {
    current: 'upload',
};

const pageSlice = createSlice({
    name: 'page',
    initialState,
    reducers: {
        setPage(state, action: PayloadAction<PageName>) {
            state.current = action.payload;
        },
        resetPage(state) {
            state.current = 'upload';
        },
    },
});

export const { setPage, resetPage } = pageSlice.actions;
export default pageSlice.reducer;
