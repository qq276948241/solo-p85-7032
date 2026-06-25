-- ========================================
-- 宠物寄养管理系统数据库初始化脚本
-- ========================================

CREATE DATABASE IF NOT EXISTS pet_care
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE pet_care;

-- ========================================
-- 门店表
-- ========================================
CREATE TABLE IF NOT EXISTS stores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    address VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    capacity INT NOT NULL DEFAULT 20,
    status ENUM('open', 'closed', 'maintenance') DEFAULT 'open',
    daily_rate FLOAT NOT NULL DEFAULT 120.0,
    hourly_rate FLOAT NOT NULL DEFAULT 20.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 主人表
-- ========================================
CREATE TABLE IF NOT EXISTS owners (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    wechat VARCHAR(50),
    email VARCHAR(100),
    address VARCHAR(255),
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 宠物表
-- ========================================
CREATE TABLE IF NOT EXISTS pets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    species VARCHAR(50) NOT NULL,
    breed VARCHAR(100),
    gender ENUM('male', 'female', 'unknown') DEFAULT 'unknown',
    birthday DATE,
    weight FLOAT,
    color VARCHAR(50),
    chip_number VARCHAR(50),
    owner_id INT NOT NULL,
    avatar_url VARCHAR(255),
    allergies TEXT,
    dietary_notes TEXT,
    behavioral_notes TEXT,
    medical_notes TEXT,
    remark TEXT,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_owner (owner_id),
    INDEX idx_species (species),
    CONSTRAINT fk_pets_owner FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 疫苗记录表
-- ========================================
CREATE TABLE IF NOT EXISTS vaccines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    manufacturer VARCHAR(100),
    batch_number VARCHAR(50),
    vaccinated_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status ENUM('valid', 'expired', 'pending') DEFAULT 'valid',
    certificate_url VARCHAR(255),
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pet (pet_id),
    INDEX idx_status (status),
    CONSTRAINT fk_vaccines_pet FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 员工表
-- ========================================
CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    id_card VARCHAR(18) UNIQUE,
    role ENUM('admin', 'manager', 'caretaker', 'receptionist') DEFAULT 'caretaker',
    store_id INT,
    avatar_url VARCHAR(255),
    hire_date DATE,
    is_active TINYINT(1) DEFAULT 1,
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone (phone),
    INDEX idx_store (store_id),
    INDEX idx_role (role),
    CONSTRAINT fk_employees_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 员工班表
-- ========================================
CREATE TABLE IF NOT EXISTS employee_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    work_date DATE NOT NULL,
    shift_type ENUM('morning', 'afternoon', 'night', 'full') NOT NULL,
    start_time VARCHAR(10),
    end_time VARCHAR(10),
    remark VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uix_emp_date_shift (employee_id, work_date, shift_type),
    INDEX idx_employee_date (employee_id, work_date),
    CONSTRAINT fk_schedules_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 寄养预约表
-- ========================================
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_no VARCHAR(32) NOT NULL UNIQUE,
    pet_id INT NOT NULL,
    store_id INT NOT NULL,
    booking_type ENUM('day_care', 'boarding', 'overnight') DEFAULT 'boarding',
    checkin_date DATE NOT NULL,
    checkout_date DATE NOT NULL,
    checkin_time VARCHAR(10),
    checkout_time VARCHAR(10),
    total_days INT NOT NULL,
    daily_rate FLOAT NOT NULL,
    extra_fee FLOAT DEFAULT 0,
    discount FLOAT DEFAULT 0,
    total_amount FLOAT NOT NULL,
    paid_amount FLOAT DEFAULT 0,
    status ENUM('pending', 'confirmed', 'checked_in', 'checked_out', 'cancelled') DEFAULT 'pending',
    pickup_person VARCHAR(50),
    pickup_phone VARCHAR(20),
    dropoff_person VARCHAR(50),
    dropoff_phone VARCHAR(20),
    items_brought TEXT,
    remark TEXT,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_booking_no (booking_no),
    INDEX idx_pet (pet_id),
    INDEX idx_store (store_id),
    INDEX idx_status (status),
    INDEX ix_booking_store_date (store_id, checkin_date, checkout_date),
    CONSTRAINT fk_bookings_pet FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE RESTRICT,
    CONSTRAINT fk_bookings_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 宠物护理员分配
-- ========================================
CREATE TABLE IF NOT EXISTS pet_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    employee_id INT NOT NULL,
    booking_id INT NOT NULL,
    assigned_date DATE NOT NULL,
    is_primary TINYINT(1) DEFAULT 1,
    remark VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pet (pet_id),
    INDEX idx_employee (employee_id),
    INDEX idx_booking (booking_id),
    CONSTRAINT fk_assignments_pet FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
    CONSTRAINT fk_assignments_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    CONSTRAINT fk_assignments_booking FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 日常照护记录表
-- ========================================
CREATE TABLE IF NOT EXISTS care_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    pet_id INT NOT NULL,
    caretaker_id INT NOT NULL,
    record_date DATE NOT NULL,
    record_time VARCHAR(10) NOT NULL,

    feeding TINYINT(1) DEFAULT 0,
    feeding_status ENUM('normal', 'little', 'none', 'refused'),
    feeding_food VARCHAR(255),
    feeding_amount VARCHAR(50),
    feeding_note VARCHAR(255),

    walking TINYINT(1) DEFAULT 0,
    walking_duration INT,
    walking_note VARCHAR(255),

    stool TINYINT(1) DEFAULT 0,
    stool_status ENUM('normal', 'soft', 'diarrhea', 'constipated', 'none'),
    stool_count INT DEFAULT 0,
    stool_note VARCHAR(255),

    water TINYINT(1) DEFAULT 0,
    water_note VARCHAR(255),

    grooming TINYINT(1) DEFAULT 0,
    grooming_note VARCHAR(255),

    mood VARCHAR(50),
    temperature FLOAT,
    weight FLOAT,

    general_note TEXT,
    abnormal_flag TINYINT(1) DEFAULT 0,
    abnormal_note TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_booking (booking_id),
    INDEX idx_pet (pet_id),
    INDEX idx_caretaker (caretaker_id),
    INDEX idx_date (record_date),
    CONSTRAINT fk_care_booking FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    CONSTRAINT fk_care_pet FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE RESTRICT,
    CONSTRAINT fk_care_caretaker FOREIGN KEY (caretaker_id) REFERENCES employees(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 照护照片
-- ========================================
CREATE TABLE IF NOT EXISTS care_photos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    care_record_id INT NOT NULL,
    photo_url VARCHAR(255) NOT NULL,
    photo_type VARCHAR(50),
    caption VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_record (care_record_id),
    CONSTRAINT fk_photos_record FOREIGN KEY (care_record_id) REFERENCES care_records(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 疫苗提醒记录表
-- ========================================
CREATE TABLE IF NOT EXISTS vaccination_reminders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vaccine_id INT NOT NULL,
    pet_id INT NOT NULL,
    owner_id INT NOT NULL,
    store_id INT,
    vaccine_name VARCHAR(100) NOT NULL,
    expiry_date DATE NOT NULL,
    days_to_expiry INT NOT NULL,
    is_expired TINYINT(1) DEFAULT 0,
    status ENUM('pending', 'notified', 'acknowledged', 'ignored') DEFAULT 'pending',
    channel ENUM('wechat', 'sms', 'phone', 'in_app', 'manual') DEFAULT 'manual',
    notified_at DATETIME,
    notified_by INT,
    note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_vaccine (vaccine_id),
    INDEX idx_pet (pet_id),
    INDEX idx_owner (owner_id),
    INDEX idx_store (store_id),
    INDEX idx_expiry (expiry_date),
    INDEX idx_status (status),
    INDEX idx_expired (is_expired),
    CONSTRAINT fk_reminder_vaccine FOREIGN KEY (vaccine_id) REFERENCES vaccines(id) ON DELETE CASCADE,
    CONSTRAINT fk_reminder_pet FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
    CONSTRAINT fk_reminder_owner FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE,
    CONSTRAINT fk_reminder_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========================================
-- 插入三家门店种子数据
-- ========================================
INSERT INTO stores (name, address, phone, capacity, status, daily_rate, hourly_rate) VALUES
('爱宠之家·朝阳店', '北京市朝阳区望京SOHO T1-101', '010-88888001', 25, 'open', 150.0, 25.0),
('萌宠乐园·海淀店', '北京市海淀区中关村大街1号', '010-88888002', 20, 'open', 130.0, 22.0),
('宠物驿站·通州店', '北京市通州区万达广场B座201', '010-88888003', 30, 'open', 120.0, 20.0)
ON DUPLICATE KEY UPDATE
    address=VALUES(address),
    phone=VALUES(phone),
    capacity=VALUES(capacity),
    status=VALUES(status),
    daily_rate=VALUES(daily_rate),
    hourly_rate=VALUES(hourly_rate);
