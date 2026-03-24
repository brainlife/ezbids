import Header from '../components/landing/Header';
import Footer from '../components/landing/Footer';

export default function NotFound() {
    return (
        <div className="flex flex-col h-screen">
            <Header />
            <main className="flex-1 flex items-center justify-center text-white">
                <div className="flex">
                    <div className="w-[4%]" />
                    <div className="flex items-center justify-center w-full h-full">
                        <div className="bg-[#20ab5c] p-8 rounded text-xl">
                            <h1>Page Not found</h1>
                            <p>The page you are looking for does not exist.</p>
                        </div>
                    </div>
                    <div className="w-[4%]" />
                </div>
            </main>
            <Footer />
        </div>
    );
}
