package in.agclms.ultraportal;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;

/**
 * Pure native zero-dependency ContentProvider to securely expose downloaded
 * APK files to Android's system Package Installer via content:// URI.
 */
public class GenericFileProvider extends ContentProvider {
    public static final String AUTHORITY = "in.agclms.ultraportal.fileprovider";

    @Override
    public boolean onCreate() {
        return true;
    }

    private File getApkFile() {
        if (getContext() == null) return null;
        File cacheFile = new File(getContext().getCacheDir(), "Krono_update.apk");
        if (cacheFile.exists() && cacheFile.length() > 0) {
            return cacheFile;
        }
        File extFile = new File(getContext().getExternalFilesDir(null), "Krono_update.apk");
        if (extFile.exists() && extFile.length() > 0) {
            return extFile;
        }
        return null;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (getContext() == null) {
            throw new FileNotFoundException("Context is null");
        }
        File apkFile = getApkFile();
        if (apkFile != null && apkFile.exists()) {
            return ParcelFileDescriptor.open(apkFile, ParcelFileDescriptor.MODE_READ_ONLY);
        }
        throw new FileNotFoundException("APK update file not found for URI: " + uri.toString());
    }

    @Override
    public String getType(Uri uri) {
        return "application/vnd.android.package-archive";
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        File apkFile = getApkFile();
        if (apkFile == null || !apkFile.exists()) {
            return null;
        }
        if (projection == null) {
            projection = new String[] { OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE };
        }
        MatrixCursor cursor = new MatrixCursor(projection, 1);
        MatrixCursor.RowBuilder row = cursor.newRow();
        for (String col : projection) {
            if (OpenableColumns.DISPLAY_NAME.equals(col)) {
                row.add(OpenableColumns.DISPLAY_NAME, "Krono.apk");
            } else if (OpenableColumns.SIZE.equals(col)) {
                row.add(OpenableColumns.SIZE, apkFile.length());
            } else {
                row.add(null);
            }
        }
        return cursor;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }
}
