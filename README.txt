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




////////////////// EDIT POINT USER DENGAN LOG //////////////////
-- STEP 1: Insert ke pilah_transaction
INSERT INTO pilah_transaction 
(user_id, type, category, amount, balance_before, balance_after, status, tid, created_at, notes)
VALUES 
(85, 'credit', 'admin_adjustment', 50, 50, 100, 'completed', 'ADMIN-ADJ-001', NOW(), 'Manual balance adjustment');

-- STEP 2: Update pilah_point
UPDATE pilah_point SET balance = 100, updated_at = NOW() WHERE user_id = 85;

-- STEP 3: Sync wp_usermeta
UPDATE wp_usermeta SET meta_value = '100' 
WHERE user_id = 85 AND meta_key = 'pilah_balance';

-- STEP 4: Log di pilah_audit_log
INSERT INTO pilah_audit_log 
(user_id, action, entity_type, entity_id, changes, created_at, admin_user)
VALUES 
(85, 'balance_adjusted', 'pilah_point', 1, 'balance: 50 → 100', NOW(), 'admin_id_here');
