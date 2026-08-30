<?php
if ( ! defined( 'ABSPATH' ) ) exit;

define( 'PILAH_USERMETA_KEY', 'pilah_balance' );

class Pilah_Usermeta_Sync {

    public static function init() {
        add_shortcode( 'pilah_balance', [ __CLASS__, 'shortcode_balance' ] );
    }

    public static function set_display_point( $user_id, $balance ) {
        update_user_meta( intval( $user_id ), PILAH_USERMETA_KEY, floatval( $balance ) );
    }

    public static function sync_from_db( $user_id ) {
        $balance = Pilah_Database::get_balance( $user_id );
        self::set_display_point( $user_id, $balance );
    }

    public static function get_display_balance( $user_id ) {
        $user_id = intval( $user_id );
        $cached  = get_user_meta( $user_id, PILAH_USERMETA_KEY, true );

        if ( $cached === '' || $cached === null || $cached === false ) {
            $balance = Pilah_Database::get_balance( $user_id );
            self::set_display_point( $user_id, $balance );
            return $balance;
        }

        return floatval( $cached );
    }

    public static function shortcode_balance( $atts ) {
        if ( ! is_user_logged_in() )
            return '<p class="pilah-error">Silakan login untuk melihat point Anda.</p>';

        $atts = shortcode_atts( [
            'label'             => 'Point Anda: ',
            'show_withdraw_btn' => 'no',
        ], $atts, 'pilah_balance' );

        $user_id = get_current_user_id();
        $balance = self::get_display_balance( $user_id );

        ob_start();

        $last_voucher = get_transient( 'pilah_last_voucher_' . $user_id );

        echo '<div class="pilah-balance-widget">';
        echo '<span class="pilah-balance-label">' . esc_html( $atts['label'] ) . '</span>';
        echo '<span class="pilah-balance-amount">' . esc_html( number_format( $balance, 0 ) ) . '</span>';

        if ( $last_voucher ) {
            echo '<div class="pilah-voucher-result">';
            echo '<p>Voucher berhasil dibuat! Kode voucher Anda:</p>';
            echo '<strong class="pilah-voucher-code">' . esc_html( $last_voucher ) . '</strong>';
            echo '</div>';
        }

        if ( 'yes' === $atts['show_withdraw_btn'] && $balance >= PILAH_MIN_WITHDRAW ) {
            echo '<div class="pilah-withdraw-btn-wrapper">';
            echo '<p>Saldo Anda cukup untuk withdraw ' . esc_html( PILAH_MIN_WITHDRAW ) . ' point.</p>';
            echo '</div>';
        }

        echo '</div>';

        if ( $last_voucher ) delete_transient( 'pilah_last_voucher_' . $user_id );

        return ob_get_clean();
    }
}
