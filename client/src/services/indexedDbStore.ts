import { openDB } from 'idb';
import type { DBSchema, IDBPDatabase } from 'idb';
import type { SavedLecture, SavedLectureMetadata } from '../types/lecture';

interface ByteClassDBSchema extends DBSchema {
  lectures: {
    key: string;
    value: SavedLecture;
    indexes: { 'by-title': string };
  };
}

const DB_NAME = 'byteclass_offline_cache';
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<ByteClassDBSchema>> | null = null;

function getDb(): Promise<IDBPDatabase<ByteClassDBSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<ByteClassDBSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('lectures')) {
          const store = db.createObjectStore('lectures', { keyPath: 'id' });
          store.createIndex('by-title', 'title');
        }
      },
    });
  }
  return dbPromise;
}

/**
 * Save binary lecture blob into client-side IndexedDB
 */
export async function saveLectureToStorage(lecture: SavedLecture): Promise<void> {
  const db = await getDb();
  await db.put('lectures', lecture);
}

/**
 * Get all cached lectures metadata from IndexedDB
 */
export async function getAllCachedLectures(): Promise<SavedLectureMetadata[]> {
  const db = await getDb();
  const all = await db.getAll('lectures');
  return all.map((item) => ({
    id: item.id,
    title: item.title,
    sourceVideoUrl: item.sourceVideoUrl,
    sourceType: item.sourceType,
    frameCount: item.frameCount,
    durationSeconds: item.durationSeconds,
    binarySizeBytes: item.binarySizeBytes,
    mp4EquivalentBytes: item.mp4EquivalentBytes,
    compressionRatio: item.compressionRatio,
    createdAt: item.createdAt,
    isCustom: item.isCustom,
  }));
}

/**
 * Retrieve full lecture including binary blob by ID
 */
export async function getLectureById(id: string): Promise<SavedLecture | undefined> {
  const db = await getDb();
  return await db.get('lectures', id);
}

/**
 * Delete a cached lecture from IndexedDB
 */
export async function deleteLectureFromStorage(id: string): Promise<void> {
  const db = await getDb();
  await db.delete('lectures', id);
}

/**
 * Clear all cached lectures
 */
export async function clearAllCachedLectures(): Promise<void> {
  const db = await getDb();
  await db.clear('lectures');
}
