import { Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import ConvertPage from './pages/ConvertPage';
import NotFound from './pages/NotFound';

export default function App() {
    return (
        <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/convert" element={<ConvertPage />} />
            <Route path="*" element={<NotFound />} />
        </Routes>
    );
}
