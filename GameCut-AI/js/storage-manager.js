/**
 * GameCut AI - Professional Storage & Permission Manager
 * Handles IndexedDB, File System Access API, and permission management
 */

const StorageManager = (() => {
    // IndexedDB setup
    const DB_NAME = 'GameCutDB';
    const DB_VERSION = 1;
    const STORES = {
        PROJECTS: 'projects',
        VIDEOS: 'videos',
        METADATA: 'metadata',
        CACHE: 'cache'
    };
    
    let db = null;
    let fileHandle = null;
    let directoryHandle = null;
    let initialized = false;

    // Initialize IndexedDB
    async function initDB() {
        if (!window.indexedDB) {
            throw new Error('IndexedDB is not supported in this browser');
        }
        return new Promise((resolve, reject) => {
            try {
                const request = indexedDB.open(DB_NAME, DB_VERSION);
                
                request.onerror = () => reject(request.error || new Error('IndexedDB open failed'));
                request.onsuccess = () => {
                    db = request.result;
                    resolve(db);
                };
                
                request.onupgradeneeded = (event) => {
                    try {
                        const database = event.target.result;
                        
                        // Projects store
                        if (!database.objectStoreNames.contains(STORES.PROJECTS)) {
                            const projectsStore = database.createObjectStore(STORES.PROJECTS, { keyPath: 'id', autoIncrement: true });
                            projectsStore.createIndex('createdAt', 'createdAt', { unique: false });
                            projectsStore.createIndex('status', 'status', { unique: false });
                        }
                        
                        // Videos store (for large video blobs)
                        if (!database.objectStoreNames.contains(STORES.VIDEOS)) {
                            const videosStore = database.createObjectStore(STORES.VIDEOS, { keyPath: 'id', autoIncrement: true });
                            videosStore.createIndex('projectId', 'projectId', { unique: false });
                            videosStore.createIndex('createdAt', 'createdAt', { unique: false });
                        }
                        
                        // Metadata store
                        if (!database.objectStoreNames.contains(STORES.METADATA)) {
                            database.createObjectStore(STORES.METADATA, { keyPath: 'key' });
                        }
                        
                        // Cache store
                        if (!database.objectStoreNames.contains(STORES.CACHE)) {
                            const cacheStore = database.createObjectStore(STORES.CACHE, { keyPath: 'key' });
                            cacheStore.createIndex('expiresAt', 'expiresAt', { unique: false });
                        }
                    } catch (e) {
                        reject(e);
                    }
                };
            } catch (e) {
                reject(e);
            }
        });
    }

    // Generic DB operations
    async function dbOperation(storeName, mode, operation) {
        if (!db) {
            try {
                await initDB();
            } catch (e) {
                throw e;
            }
        }
        if (!db) {
            throw new Error('Database not available');
        }
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = db.transaction(storeName, mode);
                const store = transaction.objectStore(storeName);
                const request = operation(store);
                
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error || new Error('DB operation failed'));
            } catch (e) {
                reject(e);
            }
        });
    }

    // Project operations
    async function saveProject(projectData) {
        if (!projectData || typeof projectData !== 'object') {
            throw new Error('Invalid project data');
        }
        const project = {
            ...projectData,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        return dbOperation(STORES.PROJECTS, 'readwrite', (store) => {
            return project.id ? store.put(project) : store.add(project);
        });
    }

    async function getProject(id) {
        if (id === undefined || id === null) throw new Error('Invalid project ID');
        return dbOperation(STORES.PROJECTS, 'readonly', (store) => store.get(id));
    }

    async function getAllProjects() {
        return dbOperation(STORES.PROJECTS, 'readonly', (store) => store.getAll());
    }

    async function deleteProject(id) {
        if (id === undefined || id === null) throw new Error('Invalid project ID');
        return dbOperation(STORES.PROJECTS, 'readwrite', (store) => store.delete(id));
    }

    // Video operations (for large files)
    async function saveVideo(projectId, videoBlob, metadata) {
        if (!projectId) throw new Error('Invalid project ID');
        if (!videoBlob) throw new Error('Invalid video blob');
        metadata = metadata || {};
        
        const videoData = {
            projectId,
            blob: videoBlob,
            size: videoBlob.size,
            type: videoBlob.type,
            ...metadata,
            createdAt: new Date().toISOString()
        };
        
        return dbOperation(STORES.VIDEOS, 'readwrite', (store) => store.add(videoData));
    }

    async function getVideo(id) {
        if (id === undefined || id === null) throw new Error('Invalid video ID');
        return dbOperation(STORES.VIDEOS, 'readonly', (store) => store.get(id));
    }

    async function deleteVideo(id) {
        if (id === undefined || id === null) throw new Error('Invalid video ID');
        return dbOperation(STORES.VIDEOS, 'readwrite', (store) => store.delete(id));
    }

    // Metadata operations
    async function setMetadata(key, value) {
        if (!key) throw new Error('Invalid metadata key');
        return dbOperation(STORES.METADATA, 'readwrite', (store) => 
            store.put({ key, value, updatedAt: new Date().toISOString() })
        );
    }

    async function getMetadata(key) {
        if (!key) return null;
        try {
            const result = await dbOperation(STORES.METADATA, 'readonly', (store) => store.get(key));
            return result ? result.value : null;
        } catch (e) {
            return null;
        }
    }

    // Cache operations
    async function setCache(key, value, ttlMs) {
        if (!key) throw new Error('Invalid cache key');
        ttlMs = ttlMs || 3600000; // Default 1 hour TTL
        const expiresAt = new Date(Date.now() + ttlMs).toISOString();
        return dbOperation(STORES.CACHE, 'readwrite', (store) => 
            store.put({ key, value, expiresAt, createdAt: new Date().toISOString() })
        );
    }

    async function getCache(key) {
        if (!key) return null;
        try {
            const result = await dbOperation(STORES.CACHE, 'readonly', (store) => store.get(key));
            
            if (!result) return null;
            
            // Check if expired
            if (new Date(result.expiresAt) < new Date()) {
                try {
                    await dbOperation(STORES.CACHE, 'readwrite', (store) => store.delete(key));
                } catch (e) {
                    // Ignore cleanup errors
                }
                return null;
            }
            
            return result.value;
        } catch (e) {
            return null;
        }
    }

    // Storage estimation
    async function getStorageEstimate() {
        if (navigator.storage && navigator.storage.estimate) {
            try {
                return await navigator.storage.estimate();
            } catch (e) {
                return null;
            }
        }
        return null;
    }

    async function getStorageUsage() {
        try {
            const estimate = await getStorageEstimate();
            if (!estimate) return null;
            
            const usage = estimate.usage || 0;
            const quota = estimate.quota || 0;
            const percent = quota ? Math.min(100, Math.round((usage / quota) * 100)) : 0;
            
            return {
                usage,
                quota,
                percent,
                usageFormatted: formatBytes(usage),
                quotaFormatted: formatBytes(quota)
            };
        } catch (e) {
            return null;
        }
    }

    // Request persistent storage
    async function requestPersistentStorage() {
        if (!navigator.storage || !navigator.storage.persist) {
            return { granted: false, reason: 'not_supported' };
        }
        
        try {
            const granted = await navigator.storage.persist();
            return { granted, reason: granted ? 'granted' : 'denied' };
        } catch (e) {
            return { granted: false, reason: 'error' };
        }
    }

    // Check if persistent storage is granted
    async function isPersistentStorageGranted() {
        if (!navigator.storage || !navigator.storage.persisted) {
            return false;
        }
        try {
            return await navigator.storage.persisted();
        } catch (e) {
            return false;
        }
    }

    // File System Access API
    async function requestFileAccess() {
        if (!('showOpenFilePicker' in window)) {
            return { granted: false, reason: 'not_supported' };
        }
        
        try {
            const [handle] = await window.showOpenFilePicker({
                types: [{
                    description: 'Video files',
                    accept: {
                        'video/*': ['.mp4', '.mov', '.mkv', '.avi', '.webm']
                    }
                }],
                multiple: false
            });
            
            fileHandle = handle;
            const file = await handle.getFile();
            
            return {
                granted: true,
                file,
                handle: fileHandle
            };
        } catch (error) {
            if (error.name === 'AbortError') {
                return { granted: false, reason: 'user_cancelled' };
            }
            return { granted: false, reason: error.message || 'unknown_error' };
        }
    }

    async function requestDirectoryAccess() {
        if (!('showDirectoryPicker' in window)) {
            return { granted: false, reason: 'not_supported' };
        }
        
        try {
            directoryHandle = await window.showDirectoryPicker();
            return { granted: true, handle: directoryHandle };
        } catch (error) {
            if (error.name === 'AbortError') {
                return { granted: false, reason: 'user_cancelled' };
            }
            return { granted: false, reason: error.message || 'unknown_error' };
        }
    }

    async function readFileFromHandle(handle) {
        if (!handle) throw new Error('Invalid file handle');
        return await handle.getFile();
    }

    async function writeFileToHandle(handle, content, filename) {
        if (!handle) throw new Error('Invalid file handle');
        const writable = await handle.createWritable();
        await writable.write(content);
        await writable.close();
    }

    // Permission checks
    async function checkPermissionStatus(permissionName) {
        if (!('permissions' in navigator)) {
            return 'unsupported';
        }
        
        try {
            const result = await navigator.permissions.query({ name: permissionName });
            return result.state; // 'granted', 'denied', 'prompt'
        } catch (error) {
            return 'unsupported';
        }
    }

    async function getAllPermissionStatuses() {
        var permissions = {
            notifications: 'unsupported',
            storage: 'available',
            files: 'not_requested',
            persistentStorage: 'available'
        };
        
        try {
            permissions.notifications = 'Notification' in window ? Notification.permission : 'unsupported';
        } catch (e) {
            permissions.notifications = 'unsupported';
        }
        
        try {
            permissions.storage = await isPersistentStorageGranted() ? 'granted' : 'available';
            permissions.persistentStorage = await isPersistentStorageGranted() ? 'granted' : 'available';
        } catch (e) {
            permissions.storage = 'available';
            permissions.persistentStorage = 'available';
        }
        
        permissions.files = fileHandle ? 'granted' : 'not_requested';
        
        return permissions;
    }

    // Cleanup operations
    async function clearExpiredCache() {
        try {
            const allCache = await dbOperation(STORES.CACHE, 'readonly', (store) => store.getAll());
            const now = new Date();
            
            for (const item of allCache) {
                if (new Date(item.expiresAt) < now) {
                    try {
                        await dbOperation(STORES.CACHE, 'readwrite', (store) => store.delete(item.key));
                    } catch (e) {
                        // Ignore individual delete errors
                    }
                }
            }
        } catch (e) {
            // Ignore cache cleanup errors
        }
    }

    async function getTotalStorageUsed() {
        try {
            const projects = await getAllProjects();
            const videos = await dbOperation(STORES.VIDEOS, 'readonly', (store) => store.getAll());
            
            let totalSize = 0;
            
            // Estimate projects size
            if (projects && Array.isArray(projects)) {
                projects.forEach(project => {
                    try {
                        totalSize += JSON.stringify(project).length;
                    } catch (e) {
                        // Ignore individual project size errors
                    }
                });
            }
            
            // Add actual video sizes
            if (videos && Array.isArray(videos)) {
                videos.forEach(video => {
                    totalSize += video.size || 0;
                });
            }
            
            return totalSize;
        } catch (e) {
            return 0;
        }
    }

    async function cleanupOldProjects(daysOld) {
        daysOld = daysOld || 30;
        try {
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - daysOld);
            
            const projects = await getAllProjects();
            if (!projects || !Array.isArray(projects)) return 0;
            
            const oldProjects = projects.filter(p => p && new Date(p.createdAt) < cutoffDate);
            
            for (const project of oldProjects) {
                try {
                    await deleteProject(project.id);
                } catch (e) {
                    // Ignore individual delete errors
                }
            }
            
            return oldProjects.length;
        } catch (e) {
            return 0;
        }
    }

    // Utility functions
    function formatBytes(bytes) {
        if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let value = bytes;
        let unit = 0;
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024;
            unit++;
        }
        return value.toFixed(unit < 2 ? 0 : 1) + ' ' + units[unit];
    }

    // Initialize on load
    async function initialize() {
        if (initialized) return true;
        try {
            await initDB();
            await clearExpiredCache();
            initialized = true;
            console.log('StorageManager initialized successfully');
            return true;
        } catch (error) {
            console.error('StorageManager initialization failed:', error);
            initialized = false;
            return false;
        }
    }

    // Public API
    return {
        // Initialization
        initialize,
        
        // Project operations
        saveProject,
        getProject,
        getAllProjects,
        deleteProject,
        
        // Video operations
        saveVideo,
        getVideo,
        deleteVideo,
        
        // Metadata
        setMetadata,
        getMetadata,
        
        // Cache
        setCache,
        getCache,
        clearExpiredCache,
        
        // Storage info
        getStorageEstimate,
        getStorageUsage,
        getTotalStorageUsed,
        requestPersistentStorage,
        isPersistentStorageGranted,
        
        // File System Access
        requestFileAccess,
        requestDirectoryAccess,
        readFileFromHandle,
        writeFileToHandle,
        
        // Permissions
        checkPermissionStatus,
        getAllPermissionStatuses,
        
        // Cleanup
        cleanupOldProjects,
        
        // Utilities
        formatBytes
    };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        StorageManager.initialize().catch(() => {});
    });
} else {
    StorageManager.initialize().catch(() => {});
}