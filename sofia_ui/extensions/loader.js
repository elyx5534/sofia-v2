/**
 * Sofia V2 Extension Loader
 * Single-file loader for all Sofia V2 extensions
 * This preserves existing UI and only adds new functionality
 */

(function() {
    'use strict';
    
    // Scripts to load in order
    const extensions = [
        '/extensions/config.js',
        '/extensions/adapter.js'
    ];
    
    // Load scripts sequentially
    function loadScript(src, callback) {
        const script = document.createElement('script');
        script.src = src;
        script.onload = callback;
        script.onerror = () => {
            console.error(`[Sofia Loader] Failed to load: ${src}`);
            callback(); // Continue anyway
        };
        document.body.appendChild(script);
    }
    
    // Load all extensions
    function loadExtensions() {
        let index = 0;
        
        function loadNext() {
            if (index < extensions.length) {
                console.log(`[Sofia Loader] Loading ${extensions[index]}`);
                loadScript(extensions[index], () => {
                    index++;
                    loadNext();
                });
            } else {
                console.log('[Sofia Loader] All extensions loaded');
                // Emit loaded event
                window.dispatchEvent(new Event('sofia:loaded'));
            }
        }
        
        loadNext();
    }
    
    // Start loading when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadExtensions);
    } else {
        loadExtensions();
    }
    
})();