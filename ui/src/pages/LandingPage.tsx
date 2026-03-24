import Header from '../components/landing/Header';
import Content from '../components/landing/Content';
import Footer from '../components/landing/Footer';

export default function LandingPage() {
    return (
        <div className="flex flex-col pb-0 h-full min-h-[750px]">
            <Header />
            <Content />
            <Footer />
        </div>
    );
}
