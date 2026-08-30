<?php
if ( ! defined( 'ABSPATH' ) ) exit;

class Pilah_Database {

    public static function get_wpdb() {
        global $wpdb;
        return $wpdb;
    }

    public static function get_user_point( $user_id ) {
        $wpdb = self::get_wpdb();
        return $wpdb->get_row(
            $wpdb->prepare(
                "SELECT * FROM pilah_point WHERE user_id = %d",
                intval( $user_id )
            )
        );
    }

    public static function get_balance( $user_id ) {
        $row = self::get_user_point( $user_id );
        return $row ? floatval( $row->balance ) : 0.0;
    }
}
