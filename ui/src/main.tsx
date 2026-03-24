import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import { library } from '@fortawesome/fontawesome-svg-core';
import { faGithub } from '@fortawesome/free-brands-svg-icons';
import {
    faSpinner,
    faAngleLeft,
    faAngleRight,
    faAngleDown,
    faEye,
    faCircleCheck,
    faArrowUpRightFromSquare,
    faCircleInfo,
    faUsers,
    faBook,
    faDownload,
} from '@fortawesome/free-solid-svg-icons';
import { Toaster } from 'react-hot-toast';

import { store } from './store';
import App from './App';
import './index.css';

// FontAwesome icons
library.add(
    faSpinner,
    faGithub,
    faAngleLeft,
    faAngleRight,
    faAngleDown,
    faEye,
    faCircleCheck,
    faArrowUpRightFromSquare,
    faCircleInfo,
    faUsers,
    faBook,
    faDownload
);

const isElectron = window.location.protocol === 'file:';

const Router = isElectron
    ? ({ children }: { children: React.ReactNode }) => <HashRouter>{children}</HashRouter>
    : ({ children }: { children: React.ReactNode }) => <BrowserRouter basename="/ezbids">{children}</BrowserRouter>;

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <Provider store={store}>
            <Router>
                <App />
                <Toaster position="top-right" />
            </Router>
        </Provider>
    </React.StrictMode>
);
