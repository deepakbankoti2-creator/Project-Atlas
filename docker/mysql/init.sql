-- =====================================================================
-- Project Atlas — MySQL Database Initialization & Seed Script
-- Database: project_atlas
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `project_atlas` 
    DEFAULT CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE `project_atlas`;

-- ---------------------------------------------------------------------
-- 1. Table: reports
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `reports` (
    `id` VARCHAR(10) NOT NULL PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `publisher` VARCHAR(100) NOT NULL,
    `published` DATE NOT NULL,
    `sector` VARCHAR(50) NOT NULL,
    `access` ENUM('paid', 'public') NOT NULL,
    INDEX `idx_sector` (`sector`),
    INDEX `idx_access` (`access`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. Table: market_metrics
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `market_metrics` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `report_id` VARCHAR(10) NULL,
    `metric` VARCHAR(100) NULL,
    `region` VARCHAR(100) NULL,
    `period` VARCHAR(50) NULL,
    `value` VARCHAR(50) NULL,
    `scope_note` TEXT NULL,
    INDEX `idx_report` (`report_id`),
    INDEX `idx_metric` (`metric`),
    CONSTRAINT `fk_metric_report` FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3. Table: clients
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `clients` (
    `id` VARCHAR(10) NOT NULL PRIMARY KEY,
    `company` VARCHAR(100) NOT NULL,
    `contact_email` VARCHAR(100) NOT NULL,
    `purchased_reports` TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 4. Table: escalations
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `escalations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `client_id` VARCHAR(10) NOT NULL,
    `query` TEXT NOT NULL,
    `reason` VARCHAR(255) NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'open',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_escalation_client` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 5. Table: conversations
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `conversations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `client_id` VARCHAR(10) NOT NULL,
    `question` TEXT NOT NULL,
    `answer` TEXT NOT NULL,
    `citations_json` LONGTEXT NULL,
    `confidence` VARCHAR(20) NULL,
    `conflicts_json` LONGTEXT NULL,
    `derived_values_json` LONGTEXT NULL,
    `escalated` TINYINT(1) NOT NULL DEFAULT 0,
    `escalation_ticket_id` VARCHAR(50) NULL,
    `route` VARCHAR(50) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_conv_client` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 6. Table: feedback
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `feedback` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `conversation_id` INT NOT NULL,
    `client_id` VARCHAR(10) NOT NULL,
    `rating` VARCHAR(10) NOT NULL,
    `comment` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_feedback_conv` (`conversation_id`),
    INDEX `idx_feedback_client` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Seed Data: reports
-- ---------------------------------------------------------------------
INSERT INTO `reports` (`id`, `title`, `publisher`, `published`, `sector`, `access`) VALUES
('R-101', 'Global Smart Water Meter Market 2025', 'CMR', '2025-03-10', 'Utilities', 'paid'),
('R-102', 'Smart Water Metering: Industry Outlook 2024', 'Aquila Insights (third party)', '2024-06-18', 'Utilities', 'public'),
('R-103', 'Residential Water Purifier Market', 'CMR', '2025-01-22', 'Consumer Durables', 'paid'),
('R-104', 'EV Battery Recycling Market 2025', 'CMR', '2025-02-14', 'CleanTech', 'paid'),
('R-105', 'Commercial Building Energy Management Systems Market 2024', 'Aquila Insights (third party)', '2024-08-11', 'Energy & Infrastructure', 'public'),
('R-106', 'Healthcare Generative AI Market 2025', 'CMR', '2025-01-15', 'Healthcare', 'paid')
ON DUPLICATE KEY UPDATE `title`=VALUES(`title`), `access`=VALUES(`access`);

-- ---------------------------------------------------------------------
-- Seed Data: market_metrics
-- ---------------------------------------------------------------------
INSERT INTO `market_metrics` (`report_id`, `metric`, `region`, `period`, `value`, `scope_note`) VALUES
('R-101', 'Market size', 'Global', '2024', 'USD 4.21 B', 'Includes hardware, software and services'),
('R-101', 'CAGR', 'Global', '2025-2030', '11.2 %', 'Forecast period stated as 2025-2030'),
('R-101', 'Regional share', 'APAC', '2024', '38 %', 'Share of global market size'),
('R-102', 'Market size', 'Global', '2024', 'USD 3.87 B', 'AMR / AMI hardware only'),
('R-102', 'CAGR', 'Global', '2024-2029', '9.8 %', 'Different forecast window from R-101'),
('R-102', 'Regional share', 'APAC', '2024', '41 %', 'Share of hardware market'),
('R-103', 'Market size', 'Global', '2024', 'USD 11.4 B', 'Point-of-use and whole house systems'),
('R-104', 'Market size', 'Global', '2024', 'USD 9.25 B', 'Hydrometallurgical and pyrometallurgical recycling'),
('R-104', 'CAGR', 'Global', '2025-2032', '21.4 %', 'Projected expansion 2025 to 2032'),
('R-104', 'Regional share', 'APAC', '2024', '52 %', 'China, Japan, South Korea cell manufacturing hub'),
('R-105', 'Market size', 'Global', '2024', 'USD 6.80 B', 'Smart HVAC controls, lighting, enterprise analytics'),
('R-105', 'CAGR', 'Global', '2024-2030', '12.5 %', 'Forecast through 2030'),
('R-105', 'Regional share', 'North America', '2024', '44 %', 'Corporate net-zero standards'),
('R-106', 'Market size', 'Global', '2024', 'USD 2.15 B', 'Clinical documentation copilots, medical imaging, triage'),
('R-106', 'CAGR', 'Global', '2025-2031', '34.8 %', 'Accelerating AI hospital adoption 2025-2031'),
('R-106', 'Regional share', 'North America', '2024', '48 %', 'Rapid health-system copilot rollouts');

-- ---------------------------------------------------------------------
-- Seed Data: clients
-- ---------------------------------------------------------------------
INSERT INTO `clients` (`id`, `company`, `contact_email`, `purchased_reports`) VALUES
('C-01', 'Northwind Utilities', 'ops@example.com', 'R-101, R-103, R-104'),
('C-02', 'Blue Delta Infra', 'procurement@example.com', 'R-103, R-106')
ON DUPLICATE KEY UPDATE `purchased_reports`=VALUES(`purchased_reports`);

-- ---------------------------------------------------------------------
-- Security: Read-Only User for Agent SQL Tool
-- ---------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'atlas_readonly'@'%' IDENTIFIED BY 'readonly_secure_password_2025';
GRANT SELECT ON `project_atlas`.* TO 'atlas_readonly'@'%';
FLUSH PRIVILEGES;
