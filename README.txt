Update yang harus dilakukan
* buat automate Trx dan wd
* Tidak boleh duplicate

*** Issue Severity Impact ***
TID duplikat no error message	🔴 CRITICAL	User tidak tahu poin gagal
Tidak ada admin dashboard	🟠 HIGH	Admin operasional jadi susah
Rate limit tidak ada feedback	🟠 HIGH	User bingung form error
Data sync inconsistency	🟠 HIGH	Poin user bisa mismatch
Hook failure no recovery	🟡 MEDIUM	Data bisa orphaned


*** ALUR SUBMIT DATA ***
Forminator Submit
    ↓
wp_frmt_form_entry* + wp_frmt_form_entry_meta*
    ↓
Hook forminator_form_after_save_entry
    ↓
pilah_transaction + pilah_point + pilah_voucher (jika withdraw)
    ↓
pilah_audit_log + pilah_rate_limit + wp_usermeta (sync)


* form id di forminator id nya sudah tercatat di plugin pilah plugin. jadi tidak bisa ganti2 id sembarangan

////////////////// EDIT POINT METADATA USER EXISTING //////////////////
Query 1: Buat di pilah_point
sql
INSERT INTO pilah_point (user_id, balance, version, updated_at)
VALUES (85, 0, 0, NOW());

👉 Ganti 85 dengan User ID Anda

Query 2: Buat di wp_usermeta
sql
INSERT INTO wp_usermeta (user_id, meta_key, meta_value)
VALUES (85, 'pilah_balance', '0');

👉 Ganti 85 dengan User ID Anda

Query 3: Verifikasi (Cek keduanya ada)
sql
SELECT * FROM pilah_point WHERE user_id = 85;
SELECT * FROM wp_usermeta WHERE user_id = 85 AND meta_key = 'pilah_balance';

👉 Ganti 85 dengan User ID Anda - harus ada muncul 2 row

✅ Testing
Login sebagai user (User ID 85)
Submit form Topup dengan TID unik (misal: TEST-001) dan amount 50
Cek database:
sql
   SELECT * FROM pilah_point WHERE user_id = 85;  -- balance harus jadi 50
   SELECT * FROM pilah_transaction WHERE user_id = 85;  -- harus ada 1 entry
Cek frontend: Refresh profile → harus tampil "Your Point: 50"
🎯 Result
✅ Sukses jika:
- pilah_point balance berubah dari 0 → 50
- wp_usermeta meta_value berubah dari 0 → 50
- pilah_transaction ada entry baru
- Frontend tampil point yang benar


////////////////// EDIT POINT USER DENGAN LOG //////////////////
START TRANSACTION;  ← MULAI TRANSACTION

-- STEP 1: Insert ke pilah_transaction
INSERT INTO pilah_transaction
(user_id, type, category, amount, balance_before, balance_after, status, tid, created_at, notes)
VALUES
(1, 'credit', 'topup', 50, 300, 350, 'completed', 'ADMIN-ADJ-001', NOW(), 'Manual balance adjustment');

-- STEP 2: Update pilah_point
UPDATE pilah_point SET balance = 350, updated_at = NOW() WHERE user_id = 1;

-- STEP 3: Sync wp_usermeta
UPDATE wp_usermeta SET meta_value = '350' 
WHERE user_id = 1 AND meta_key = 'pilah_balance';

-- STEP 4: Log di pilah_audit_log
INSERT INTO pilah_audit_log 
(user_id, action, entity_type, entity_id, old_value, new_value, created_at, user_agent)
VALUES 
(1, 'balance_adjusted', 'pilah_point', 1, '300', '350', NOW(), 'admin-manual-edit');

COMMIT;  ← COMMIT JIKA SEMUA BERHASIL
-- Jika ada error, database auto-ROLLBACK