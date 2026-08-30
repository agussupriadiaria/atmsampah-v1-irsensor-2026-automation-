<?php
/**
 * Plugin Name: Pilah Points
 * Description: Sistem point dan voucher terintegrasi untuk ATM Sampah
 * Version:     1.0.1
 * Author:      Your Name
 */

if ( ! defined( 'ABSPATH' ) ) exit;

// Konstanta path
define( 'PILAH_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'PILAH_PLUGIN_URL', plugin_dir_url( __FILE__ ) );
define( 'PILAH_VERSION',    '1.0.1' );

define( 'PILAH_MIN_WITHDRAW',      300 ); // Minimum point untuk withdraw
define( 'PILAH_RATE_LIMIT_TOPUP',   10 ); // Maks topup per jam
define( 'PILAH_RATE_LIMIT_WITHDRAW', 3 ); // Maks withdraw per jam

// Load semua class
require_once PILAH_PLUGIN_DIR . 'includes/class-database.php';
require_once PILAH_PLUGIN_DIR . 'includes/class-security.php';
require_once PILAH_PLUGIN_DIR . 'includes/class-voucher.php';
require_once PILAH_PLUGIN_DIR . 'includes/class-usermeta-sync.php';
require_once PILAH_PLUGIN_DIR . 'includes/class-point-handler.php';
require_once PILAH_PLUGIN_DIR . 'includes/class-forminator-hook.php';

// Inisialisasi semua class saat WordPress load
add_action( 'plugins_loaded', function() {
    Pilah_Point_Handler::init();
    Pilah_Forminator_Hook::init();
    Pilah_Usermeta_Sync::init();
});

register_activation_hook( __FILE__, 'pilah_on_activation' );
function pilah_on_activation() {
    global $wpdb;
    $charset = $wpdb->get_charset_collate();

    $sqls = [
        "CREATE TABLE IF NOT EXISTS pilah_point (
            id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id    BIGINT UNSIGNED NOT NULL,
            balance    DECIMAL(10,2)   NOT NULL DEFAULT 0.00,
            version    INT UNSIGNED    NOT NULL DEFAULT 0,
            updated_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uq_user (user_id)
        ) ENGINE=InnoDB {$charset};",

        "CREATE TABLE IF NOT EXISTS pilah_transaction (
            id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id              BIGINT UNSIGNED NOT NULL,
            type                 ENUM('credit','debit') NOT NULL,
            category             ENUM('registration','topup','withdraw','bonus','adjustment') NOT NULL,
            amount               DECIMAL(10,2) NOT NULL,
            balance_before       DECIMAL(10,2) NOT NULL,
            balance_after        DECIMAL(10,2) NOT NULL,
            status               ENUM('pending','completed','failed','rejected','flagged') NOT NULL DEFAULT 'pending',
            tid                  VARCHAR(64)  NULL,
            idempotency_key      VARCHAR(128) NULL,
            forminator_entry_id  BIGINT UNSIGNED NULL,
            ref_voucher_id       BIGINT UNSIGNED NULL,
            notes                TEXT NULL,
            ip_address           VARCHAR(45)  NULL,
            user_agent           VARCHAR(500) NULL,
            created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uq_idempotency (idempotency_key),
            UNIQUE KEY uq_tid (tid),
            KEY idx_user_id (user_id),
            KEY idx_category (category),
            KEY idx_status (status)
        ) ENGINE=InnoDB {$charset};",

        "CREATE TABLE IF NOT EXISTS pilah_voucher (
            id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id         BIGINT UNSIGNED NOT NULL,
            transaction_id  BIGINT UNSIGNED NOT NULL,
            code            VARCHAR(16)  NOT NULL,
            point_value     DECIMAL(10,2) NOT NULL,
            status          ENUM('active','used','cancelled','flagged') NOT NULL DEFAULT 'active',
            used_at         DATETIME NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uq_code (code),
            KEY idx_user_id (user_id)
        ) ENGINE=InnoDB {$charset};",

        "CREATE TABLE IF NOT EXISTS pilah_audit_log (
            id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id      BIGINT UNSIGNED NOT NULL,
            action       VARCHAR(64)  NOT NULL,
            entity_type  VARCHAR(32)  NOT NULL,
            entity_id    BIGINT UNSIGNED NOT NULL,
            old_value    JSON NULL,
            new_value    JSON NULL,
            ip_address   VARCHAR(45)  NULL,
            user_agent   VARCHAR(500) NULL,
            created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY idx_user_id (user_id),
            KEY idx_action (action)
        ) ENGINE=InnoDB {$charset};",

        "CREATE TABLE IF NOT EXISTS pilah_rate_limit (
            id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id      BIGINT UNSIGNED NOT NULL,
            action       VARCHAR(64) NOT NULL,
            count        INT UNSIGNED NOT NULL DEFAULT 0,
            window_start DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uq_user_action (user_id, action)
        ) ENGINE=InnoDB {$charset};",
    ];

    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    foreach ( $sqls as $sql ) {
        dbDelta( $sql );
    }

    // Untuk instalasi yang sudah ada: tambahkan kolom ip_address & user_agent
    // ke pilah_transaction jika belum ada (upgrade dari v1.0.0)
    $columns = $wpdb->get_results( "SHOW COLUMNS FROM pilah_transaction LIKE 'ip_address'" );
    if ( empty( $columns ) ) {
        $wpdb->query( "ALTER TABLE pilah_transaction ADD COLUMN ip_address VARCHAR(45) NULL AFTER notes, ADD COLUMN user_agent VARCHAR(500) NULL AFTER ip_address" );
    }

    error_log( '[Pilah Points] Plugin activated at ' . current_time( 'mysql' ) );
}
